( function () {
	'use strict';

	const pickerCore = window.ErenshorSemanticLinkPickerCore;
	if ( !pickerCore ) {
		throw new Error( 'Erenshor semantic-link picker core was not loaded' );
	}
	const KINDS = pickerCore.KINDS;
	const TEMPLATE_BY_KIND = pickerCore.TEMPLATE_BY_KIND;
	const displayKind = pickerCore.displayKind;
	const normalizeQuery = pickerCore.normalizeQuery;
	const kindForTemplate = pickerCore.kindForTemplate;
	const identityFromParameters = pickerCore.identityFromParameters;
	const selectionContainsStructuredWikitext = pickerCore.selectionContainsStructuredWikitext;
	const tokenizeSourceWindow = pickerCore.tokenizeSourceWindow;
	const selectionTouchesOpaqueRange = pickerCore.selectionTouchesOpaqueRange;
	const findBalancedRangeAt = pickerCore.findBalancedRangeAt;
	const parseSourceTemplate = pickerCore.parseSourceTemplate;
	const buildSourceTemplate = pickerCore.buildSourceTemplate;
	const identityTextOverride = pickerCore.identityTextOverride;
	const existingTargetMetadata = pickerCore.existingTargetMetadata;
	const validateSearchResponse = pickerCore.validateSearchResponse;
	const nextActiveIndex = pickerCore.nextActiveIndex;
	const selectionTransition = pickerCore.selectionTransition;

	const DIALOG_TITLE = 'Insert Erenshor link';
	const FAILURE_TEXT = 'Unable to load Erenshor links. Existing manual links are still available.';
	const APPLY_FAILURE_TEXT = 'Unable to update this editor. Existing content was not changed.';
	const SEARCH_DEBOUNCE_MS = 200;
	const MAX_QUERY_LENGTH = 200;
	const KIND_OPTIONS = [ { data: '', label: 'Any' } ].concat( KINDS.map( function ( kind ) {
		return { data: kind, label: displayKind( kind ) };
	} ) );
	const CORE_MODULES = [
		'mediawiki.api',
		'jquery.textSelection',
		'oojs-ui-core',
		'oojs-ui-widgets',
		'oojs-ui-windows',
		'oojs-ui.styles.icons-interactions'
	];
	const searchCache = new Map();
	const wikiEditorTextareas = new WeakSet();
	const sourceFallbacks = new WeakMap();

	let corePromise = null;
	let windowManager = null;
	let pickerDialog = null;
	let visualEditorRegistered = false;

	registerWikiEditorHook();
	registerVisualEditorHook();
	whenDocumentReady( initializePlainTextareaFallback );

	function ensureCore() {
		if ( !corePromise ) {
			corePromise = mw.loader.using( CORE_MODULES );
		}
		return corePromise;
	}

	function whenDocumentReady( callback ) {
		if ( document.readyState === 'loading' ) {
			document.addEventListener( 'DOMContentLoaded', callback, { once: true } );
		} else {
			callback();
		}
	}

	function registerWikiEditorHook() {
		mw.hook( 'wikiEditor.toolbarReady' ).add( function ( $textarea ) {
			ensureCore().then( function () {
				addWikiEditorTool( $textarea );
			}, function () {
				// If editor dependencies are unavailable, leave the editor untouched.
			} );
		} );
	}

	function addWikiEditorTool( $textarea ) {
		const textarea = $textarea && $textarea[ 0 ];
		if ( !textarea || wikiEditorTextareas.has( textarea ) || typeof $textarea.wikiEditor !== 'function' ) {
			return;
		}

		wikiEditorTextareas.add( textarea );
		removePlainTextareaFallback( textarea );
		$textarea.wikiEditor( 'addToToolbar', {
			section: 'main',
			group: 'insert',
			tools: {
				erenshorLink: {
					label: 'Erenshor link',
					type: 'button',
					oouiIcon: 'link',
					action: {
						type: 'callback',
						execute: function ( context ) {
							openSourcePicker( context.$textarea );
						}
					}
				}
			}
		} );
	}

	function initializePlainTextareaFallback() {
		if ( [ 'edit', 'submit' ].indexOf( mw.config.get( 'wgAction' ) ) === -1 ) {
			return;
		}

		const $textarea = jQuery( '#wpTextbox1' );
		if ( !$textarea.length ) {
			return;
		}

		ensureCore().then( function () {
			const textarea = $textarea[ 0 ];
			if ( wikiEditorTextareas.has( textarea ) || sourceFallbacks.has( textarea ) ) {
				return;
			}

			const button = new OO.ui.ButtonWidget( {
				label: 'Erenshor link',
				icon: 'link'
			} );
			const layout = new OO.ui.HorizontalLayout( { items: [ button ] } );
			button.on( 'click', function () {
				openSourcePicker( $textarea );
			} );
			layout.$element.addClass( 'semantic-link-picker-source-fallback' );
			$textarea.before( layout.$element );
			sourceFallbacks.set( textarea, layout );
		}, function () {
			// A plain textarea remains fully usable if optional UI modules cannot load.
		} );
	}

	function removePlainTextareaFallback( textarea ) {
		const fallback = sourceFallbacks.get( textarea );
		if ( fallback ) {
			fallback.$element.remove();
			sourceFallbacks.delete( textarea );
		}
	}

	function openSourcePicker( $textarea ) {
		const target = captureSourceTarget( $textarea );
		if ( !target ) {
			mw.notify( 'Place the cursor in plain text or a recognized Erenshor link template.', {
				type: 'warn'
			} );
			return;
		}
		openPicker( target );
	}

	function captureSourceTarget( $textarea ) {
		const contents = $textarea.textSelection( 'getContents' );
		const range = $textarea.textSelection( 'getCaretPosition', { startAndEnd: true } );
		const start = range[ 0 ];
		const end = range[ 1 ];
		const sourceTokens = tokenizeSourceWindow( contents, start, end );
		if ( selectionTouchesOpaqueRange( sourceTokens.opaqueRanges, start, end ) ) {
			return null;
		}
		const invocation = findBalancedRangeAt( contents, start, end, '{{', '}}', sourceTokens );

		if ( invocation ) {
			const parsed = parseSourceTemplate( contents.slice( invocation.start, invocation.end ) );
			if ( !parsed || !parsed.kind ) {
				return null;
			}
			return sourceTemplateTarget( $textarea, contents, invocation, parsed );
		}

		if ( findBalancedRangeAt( contents, start, end, '[[', ']]', sourceTokens ) ) {
			return null;
		}

		const selectedText = contents.slice( start, end );
		if ( selectionContainsStructuredWikitext( selectedText ) ) {
			return null;
		}

		return {
			mode: 'insert',
			actionLabel: 'Insert',
			kind: '',
			query: selectedText,
			existingText: null,
			customLabel: selectedText.trim() ? selectedText : null,
			labelResolved: true,
			learnExistingRecord: function () {},
			resolveLabelForResult: function () {},
			apply: function ( result, label ) {
				if ( $textarea.textSelection( 'getContents' ) !== contents ) {
					return false;
				}
				const replacement = buildSourceTemplate( null, result, label );
				$textarea.textSelection( 'setSelection', { start: start, end: end } );
				$textarea.textSelection( 'replaceSelection', replacement );
				$textarea.textSelection( 'setSelection', {
					start: start + replacement.length,
					end: start + replacement.length
				} );
				$textarea.textSelection( 'scrollToCaretPosition' );
				return true;
			}
		};
	}

	function sourceTemplateTarget( $textarea, contents, invocation, parsed ) {
		const metadata = existingTargetMetadata( parsed.kind, parsed.identity );
		return {
			mode: metadata.hasStableKey ? 'replace' : 'upgrade',
			actionLabel: metadata.hasStableKey ? 'Replace' : 'Upgrade to stable key',
			kind: parsed.kind,
			query: metadata.query,
			existingText: metadata.existingText,
			customLabel: metadata.customLabel,
			labelResolved: metadata.labelResolved,
			learnExistingRecord: metadata.learnExistingRecord,
			resolveLabelForResult: metadata.resolveLabelForResult,
			apply: function ( result, label ) {
				if ( $textarea.textSelection( 'getContents' ) !== contents ) {
					return false;
				}
				const replacement = buildSourceTemplate( parsed, result, label );
				$textarea.textSelection( 'setSelection', {
					start: invocation.start,
					end: invocation.end
				} );
				$textarea.textSelection( 'replaceSelection', replacement );
				$textarea.textSelection( 'setSelection', {
					start: invocation.start + replacement.length,
					end: invocation.start + replacement.length
				} );
				$textarea.textSelection( 'scrollToCaretPosition' );
				return true;
			}
		};
	}


	function registerVisualEditorHook() {
		mw.hook( 've.loadModules' ).add( function ( addPlugin ) {
			addPlugin( function () {
				return mw.loader.using( [
					'mediawiki.util',
					'ext.visualEditor.mwtransclusion'
				] ).then( function () {
					return ensureCore().then( registerVisualEditor );
				} );
			} );
		} );
	}

	function registerVisualEditor() {
		if ( visualEditorRegistered || !window.ve || !ve.ui || !ve.dm ) {
			return;
		}
		visualEditorRegistered = true;

		function ErenshorLinkCommand() {
			ErenshorLinkCommand.parent.call( this, 'erenshorLink', null, null, {
				supportedSelections: [ 'linear' ]
			} );
		}
		OO.inheritClass( ErenshorLinkCommand, ve.ui.Command );
		ErenshorLinkCommand.prototype.execute = function ( surface ) {
			if ( typeof surface.getMode === 'function' && surface.getMode() !== 'visual' ) {
				return false;
			}
			const target = captureVisualTarget( surface );
			if ( !target ) {
				mw.notify( 'Place the cursor in plain text or a recognized Erenshor link template.', {
					type: 'warn'
				} );
				return false;
			}
			openPicker( target );
			return true;
		};
		ve.ui.commandRegistry.register( new ErenshorLinkCommand() );

		function ErenshorLinkTool() {
			ErenshorLinkTool.parent.apply( this, arguments );
		}
		OO.inheritClass( ErenshorLinkTool, ve.ui.Tool );
		ErenshorLinkTool.static.name = 'erenshorLink';
		ErenshorLinkTool.static.group = 'insert';
		ErenshorLinkTool.static.title = 'Erenshor link';
		ErenshorLinkTool.static.icon = 'link';
		ErenshorLinkTool.static.commandName = 'erenshorLink';
		ErenshorLinkTool.static.deactivateOnSelect = false;
		ErenshorLinkTool.prototype.onUpdateState = function () {
			ErenshorLinkTool.parent.prototype.onUpdateState.apply( this, arguments );
			this.setActive( false );
		};
		ve.ui.toolFactory.register( ErenshorLinkTool );
	}

	function captureVisualTarget( surface ) {
		const surfaceModel = surface.getModel();
		const fragment = surfaceModel.getFragment();
		const node = fragment.getSelectedNode();

		if ( node && node.getType() === 'mwTransclusionInline' ) {
			const parts = node.getPartsList();
			if ( parts.length !== 1 || !parts[ 0 ].template ) {
				return null;
			}
			const kind = kindForTemplate( parts[ 0 ].templatePage || parts[ 0 ].template );
			if ( !kind ) {
				return null;
			}
			const mwData = node.getAttribute( 'mw' );
			if ( !mwData || !Array.isArray( mwData.parts ) || mwData.parts.length !== 1 ||
				!mwData.parts[ 0 ].template || typeof mwData.parts[ 0 ].template.params !== 'object' ) {
				return null;
			}
			return visualTemplateTarget(
				surfaceModel,
				node,
				kind,
				mwData.parts[ 0 ].template.params
			);
		}
		if ( node && node.getType() !== 'text' &&
			!( fragment.getSelection().isCollapsed() && node.getType() === 'paragraph' ) ) {
			return null;
		}

		if ( fragmentContainsProtectedModel( fragment ) || fragmentHasOrdinaryLink( fragment ) ) {
			return null;
		}

		const selectedText = fragment.getSelection().isCollapsed() ? '' : fragment.getText();
		return {
			mode: 'insert',
			actionLabel: 'Insert',
			kind: '',
			query: selectedText,
			existingText: null,
			customLabel: selectedText.trim() ? selectedText : null,
			labelResolved: true,
			learnExistingRecord: function () {},
			resolveLabelForResult: function () {},
			apply: function ( result, label ) {
				return insertVisualTemplate( surfaceModel, fragment, result, label );
			}
		};
	}

	function fragmentContainsProtectedModel( fragment ) {
		return fragment.getSelectedModels( true ).some( function ( model ) {
			const type = model.getType();
			return type === 'link/mwInternal' || type === 'link/mwExternal' ||
				type.indexOf( 'mwTransclusion' ) === 0;
		} );
	}

	function fragmentHasOrdinaryLink( fragment ) {
		let hasLink = false;
		fragment.getAnnotations( true ).filter( function ( annotation ) {
			const type = annotation.getType();
			if ( type === 'link/mwInternal' || type === 'link/mwExternal' ) {
				hasLink = true;
			}
			return false;
		} );
		return hasLink;
	}

	function visualTemplateTarget( surfaceModel, node, kind, params ) {
		const identity = identityFromVisualParameters( params, kind );
		const metadata = existingTargetMetadata( kind, identity );
		const originalMw = JSON.stringify( node.getAttribute( 'mw' ) );
		return {
			mode: metadata.hasStableKey ? 'replace' : 'upgrade',
			actionLabel: metadata.hasStableKey ? 'Replace' : 'Upgrade to stable key',
			kind: kind,
			query: metadata.query,
			existingText: metadata.existingText,
			customLabel: metadata.customLabel,
			labelResolved: metadata.labelResolved,
			learnExistingRecord: metadata.learnExistingRecord,
			resolveLabelForResult: metadata.resolveLabelForResult,
			apply: function ( result, label ) {
				return replaceVisualTemplate( surfaceModel, node, originalMw, kind, result, label );
			}
		};
	}

	function identityFromVisualParameters( params, kind ) {
		const parsed = Object.keys( params || {} ).map( function ( name ) {
			return {
				name: name,
				value: params[ name ] && typeof params[ name ].wt === 'string' ? params[ name ].wt : ''
			};
		} );
		return identityFromParameters( parsed, kind );
	}

	function insertVisualTemplate( surfaceModel, fragment, result, label ) {
		const transclusion = new ve.dm.MWTransclusionModel( surfaceModel.getDocument() );
		const template = ve.dm.MWTemplateModel.newFromName( transclusion, TEMPLATE_BY_KIND[ result.kind ] );
		if ( !template ) {
			return Promise.resolve( false );
		}
		addVisualIdentityParameters( template, result, label );
		return Promise.resolve( transclusion.addPart( template ) ).then( function () {
			return Promise.resolve( transclusion.insertTransclusionNode( fragment, 'inline' ) ).then( function () {
				return true;
			} );
		}, function () {
			return false;
		} );
	}

	function replaceVisualTemplate( surfaceModel, node, originalMw, originalKind, result, label ) {
		const documentModel = surfaceModel.getDocument();
		if ( !currentVisualNodeRange( documentModel, node, originalMw ) ) {
			return Promise.resolve( false );
		}

		const oldTransclusion = new ve.dm.MWTransclusionModel( documentModel );
		return Promise.resolve( oldTransclusion.load( node.getAttribute( 'mw' ) ) ).then( function () {
			const parts = oldTransclusion.getParts();
			if ( parts.length !== 1 || !( parts[ 0 ] instanceof ve.dm.MWTemplateModel ) ||
				kindForTemplate( parts[ 0 ].getTitle() || parts[ 0 ].getTarget().wt ) !== originalKind ) {
				return false;
			}

			const newTransclusion = new ve.dm.MWTransclusionModel( documentModel );
			const targetTemplate = ve.dm.MWTemplateModel.newFromName(
				newTransclusion,
				TEMPLATE_BY_KIND[ result.kind ]
			);
			if ( !targetTemplate ) {
				return false;
			}
			const data = replacementVisualTemplateData( parts[ 0 ], targetTemplate, originalKind, result, label );
			const replacement = ve.dm.MWTemplateModel.newFromData( newTransclusion, data );
			return Promise.resolve( newTransclusion.addPart( replacement ) ).then( function () {
				const currentRange = currentVisualNodeRange( documentModel, node, originalMw );
				if ( !currentRange ) {
					return false;
				}
				const object = newTransclusion.getPlainObject();
				if ( !object ) {
					return false;
				}
				surfaceModel.getLinearFragment( currentRange, true ).changeAttributes( { mw: object } );
				return true;
			} );
		}, function () {
			return false;
		} );
	}

	function currentVisualNodeRange( documentModel, node, originalMw ) {
		try {
			if ( node.getDocument() !== documentModel || node.getRoot() !== documentModel.getDocumentNode() ||
				JSON.stringify( node.getAttribute( 'mw' ) ) !== originalMw ) {
				return null;
			}
			const range = node.getOuterRange();
			const selectedNodes = documentModel.selectNodes( range, 'covered' );
			const attachedAtRange = selectedNodes.some( function ( selection ) {
				return selection.node === node && selection.nodeOuterRange &&
					selection.nodeOuterRange.start === range.start && selection.nodeOuterRange.end === range.end;
			} );
			return attachedAtRange ? range : null;
		} catch ( error ) {
			return null;
		}
	}

	function replacementVisualTemplateData( oldTemplate, targetTemplate, oldKind, result, label ) {
		const serialized = oldTemplate.serialize().template;
		const parameterModels = oldTemplate.getParameters();
		const identityParams = visualIdentityParameterData( result, label );
		const params = {};
		let identityWritten = false;

		Object.keys( parameterModels ).forEach( function ( name ) {
			const parameter = parameterModels[ name ];
			if ( !parameter.getName() ) {
				return;
			}
			const originalName = parameter.getOriginalName();
			if ( visualParameterIsIdentity( parameter, oldKind ) ) {
				if ( !identityWritten ) {
					copyOwnProperties( params, identityParams );
					identityWritten = true;
				}
				return;
			}
			params[ originalName ] = Object.assign( {}, serialized.params[ originalName ] );
		} );
		if ( !identityWritten ) {
			const preserved = Object.assign( {}, params );
			Object.keys( params ).forEach( function ( name ) {
				delete params[ name ];
			} );
			copyOwnProperties( params, identityParams );
			copyOwnProperties( params, preserved );
		}
		return {
			target: targetTemplate.getTarget(),
			params: params
		};
	}

	function visualParameterIsIdentity( parameter, kind ) {
		const name = parameter.getName().toLowerCase();
		return [ 'stablekey', 'key', 'link', 'page', 'text', 'image', '1' ].indexOf( name ) !== -1 ||
			kind === 'item' && [ 'item', 'name' ].indexOf( name ) !== -1;
	}

	function visualIdentityParameterData( result, label ) {
		const params = {
			stablekey: { wt: result.key }
		};
		const text = identityTextOverride( result, label );
		if ( text !== null ) {
			params.text = { wt: text };
		}
		return params;
	}

	function copyOwnProperties( target, source ) {
		Object.keys( source ).forEach( function ( key ) {
			target[ key ] = source[ key ];
		} );
	}

	function addVisualIdentityParameters( template, result, label ) {
		const params = visualIdentityParameterData( result, label );
		Object.keys( params ).forEach( function ( name ) {
			template.addParameter( new ve.dm.MWParameterModel( template, name, params[ name ].wt ) );
		} );
	}

	function openPicker( target ) {
		ensureCore().then( function () {
			ensureDialog();
			windowManager.openWindow( pickerDialog, { target: target } );
		}, function () {
			// The editor remains unchanged when the dialog cannot be loaded.
		} );
	}

	function ensureDialog() {
		if ( pickerDialog ) {
			return;
		}

		function SemanticLinkDialog( config ) {
			SemanticLinkDialog.parent.call( this, config );
			this.api = new mw.Api();
			this.requestSerial = 0;
			this.searchTimer = null;
			this.results = [];
			this.activeIndex = -1;
			this.selectedIndex = -1;
			this.selectedResult = null;
			this.target = null;
			this.suppressChanges = false;
			this.suppressLabelChange = false;
			this.labelUserEdited = false;
		}
		OO.inheritClass( SemanticLinkDialog, OO.ui.ProcessDialog );
		SemanticLinkDialog.static.name = 'semanticLinkPicker';
		SemanticLinkDialog.static.title = DIALOG_TITLE;
		SemanticLinkDialog.static.size = 'medium';
		SemanticLinkDialog.static.actions = [
			{ action: 'cancel', label: 'Cancel', flags: 'safe' },
			{ action: 'submit', label: 'Insert', flags: [ 'primary', 'progressive' ], disabled: true }
		];

		SemanticLinkDialog.prototype.initialize = function () {
			SemanticLinkDialog.parent.prototype.initialize.call( this );
			this.panel = new OO.ui.PanelLayout( { padded: true, expanded: false } );
			this.searchInput = new OO.ui.TextInputWidget( {
				placeholder: 'Name, page, or stable key',
				maxLength: MAX_QUERY_LENGTH
			} );
			this.kindInput = new OO.ui.DropdownInputWidget( { options: KIND_OPTIONS } );
			this.labelInput = new OO.ui.TextInputWidget( { maxLength: MAX_QUERY_LENGTH } );
			this.searchField = new OO.ui.FieldLayout( this.searchInput, {
				label: 'Search',
				align: 'top'
			} );
			this.kindField = new OO.ui.FieldLayout( this.kindInput, {
				label: 'Kind',
				align: 'top'
			} );
			this.labelField = new OO.ui.FieldLayout( this.labelInput, {
				label: 'Link text',
				align: 'top',
				help: 'Changing this only customizes the visible text.'
			} );
			this.resultListId = OO.ui.generateElementId();
			this.$filters = jQuery( '<div>' ).addClass( 'semantic-link-picker__filters' );
			this.$results = jQuery( '<div>' ).addClass( 'semantic-link-picker__results' ).attr( {
				id: this.resultListId,
				role: 'listbox',
				'aria-label': 'Erenshor link results',
				'aria-busy': 'false'
			} );
			this.$status = jQuery( '<div>' ).addClass( 'semantic-link-picker__status' ).attr( {
				role: 'status',
				'aria-live': 'polite',
				'aria-atomic': 'true'
			} );
			this.searchInput.$input.attr( {
				role: 'combobox',
				'aria-autocomplete': 'list',
				'aria-expanded': 'false',
				'aria-controls': this.resultListId,
				'aria-haspopup': 'listbox'
			} );
			this.$filters.append( this.searchField.$element, this.kindField.$element );
			this.labelField.$element.hide();
			this.panel.$element
				.addClass( 'semantic-link-picker__content' )
				.append( this.$filters, this.$status, this.$results, this.labelField.$element );
			this.$body.append( this.panel.$element );
			this.$element.addClass( 'semantic-link-picker-dialog' );

			this.searchInput.on( 'change', this.onSearchChange.bind( this ) );
			this.kindInput.on( 'change', this.onSearchChange.bind( this ) );
			this.labelInput.on( 'change', this.onLabelChange.bind( this ) );
			this.searchInput.$input.on( 'keydown', this.onSearchKeyDown.bind( this ) );
		};

		SemanticLinkDialog.prototype.getBodyHeight = function () {
			return this.panel.$element.outerHeight( true );
		};

		SemanticLinkDialog.prototype.getSetupProcess = function ( data ) {
			return SemanticLinkDialog.parent.prototype.getSetupProcess.call( this, data ).next( function () {
				this.target = data.target;
				this.requestSerial++;
				this.clearSearchTimer();
				this.clearResults();
				this.labelUserEdited = false;
				this.suppressChanges = true;
				this.searchInput.setValue( this.target.query || '' );
				this.kindInput.setValue( this.target.kind || '' );
				this.suppressChanges = false;
				this.setLabelValue( this.target.customLabel || '' );
				this.labelField.$element.hide();
				this.setSubmitLabel( this.target.actionLabel );
				this.actions.setAbilities( { submit: false } );
				this.scheduleSearch();
			}, this );
		};

		SemanticLinkDialog.prototype.getReadyProcess = function ( data ) {
			return SemanticLinkDialog.parent.prototype.getReadyProcess.call( this, data ).next( function () {
				this.searchInput.focus();
			}, this );
		};

		SemanticLinkDialog.prototype.getTeardownProcess = function ( data ) {
			return SemanticLinkDialog.parent.prototype.getTeardownProcess.call( this, data ).first( function () {
				this.requestSerial++;
				this.clearSearchTimer();
				this.searchInput.$input.removeAttr( 'aria-activedescendant' ).attr( 'aria-expanded', 'false' );
				this.target = null;
			}, this );
		};

		SemanticLinkDialog.prototype.getActionProcess = function ( action ) {
			if ( action === 'cancel' ) {
				return new OO.ui.Process( function () {
					this.close( { action: action } );
				}, this );
			}
			if ( action === 'submit' ) {
				return new OO.ui.Process( function () {
					if ( !this.selectedResult || !this.target ) {
						return;
					}
					this.actions.setAbilities( { submit: false } );
					const result = this.selectedResult;
					const label = this.labelInput.getValue();
					return Promise.resolve( this.target.apply( result, label ) ).then( function ( applied ) {
						if ( applied ) {
							this.close( { action: action } );
							return;
						}
						this.setStatus( APPLY_FAILURE_TEXT, true );
						this.actions.setAbilities( { submit: true } );
					}.bind( this ), function () {
						this.setStatus( APPLY_FAILURE_TEXT, true );
						this.actions.setAbilities( { submit: true } );
					}.bind( this ) );
				}, this );
			}
			return SemanticLinkDialog.parent.prototype.getActionProcess.call( this, action );
		};

		SemanticLinkDialog.prototype.setSubmitLabel = function ( label ) {
			const submitActions = this.actions.get( { actions: 'submit' } );
			if ( submitActions.length ) {
				submitActions[ 0 ].setLabel( label );
			}
		};

		SemanticLinkDialog.prototype.onSearchChange = function () {
			if ( !this.suppressChanges ) {
				this.scheduleSearch();
			}
		};

		SemanticLinkDialog.prototype.onLabelChange = function () {
			if ( !this.suppressLabelChange ) {
				this.labelUserEdited = true;
			}
		};

		SemanticLinkDialog.prototype.setLabelValue = function ( value ) {
			this.suppressLabelChange = true;
			this.labelInput.setValue( value );
			this.suppressLabelChange = false;
		};

		SemanticLinkDialog.prototype.scheduleSearch = function () {
			const query = normalizeQuery( this.searchInput.getValue() );
			const kind = this.kindInput.getValue();
			const serial = ++this.requestSerial;
			this.clearSearchTimer();
			this.clearResults();

			if ( query.length < 2 ) {
				this.setStatus( 'Enter at least two characters to search.', false );
				return;
			}

			const cacheKey = kind + '\u0000' + query;
			if ( searchCache.has( cacheKey ) ) {
				this.acceptResults( searchCache.get( cacheKey ), serial );
				return;
			}

			this.setStatus( 'Loading Erenshor links…', false );
			this.$results.attr( 'aria-busy', 'true' );
			this.searchTimer = window.setTimeout( function () {
				this.searchTimer = null;
				this.requestResults( query, kind, cacheKey, serial );
			}.bind( this ), SEARCH_DEBOUNCE_MS );
		};

		SemanticLinkDialog.prototype.requestResults = function ( query, kind, cacheKey, serial ) {
			const invocation = '{{#invoke:Erenshor/Link/Search|query|q=' + encodeURIComponent( query ) +
				'|kind=' + encodeURIComponent( kind ) + '}}';
			this.api.get( {
				action: 'expandtemplates',
				text: invocation,
				prop: 'wikitext',
				title: mw.config.get( 'wgPageName' ),
				formatversion: 2
			} ).then( function ( response ) {
				if ( serial !== this.requestSerial ) {
					return;
				}
				let results;
				try {
					results = validateSearchResponse( response );
				} catch ( error ) {
					this.failSearch( serial );
					return;
				}
				searchCache.set( cacheKey, results );
				this.acceptResults( results, serial );
			}.bind( this ), function () {
				this.failSearch( serial );
			}.bind( this ) );
		};

		SemanticLinkDialog.prototype.acceptResults = function ( results, serial ) {
			if ( serial !== this.requestSerial ) {
				return;
			}
			this.$results.attr( 'aria-busy', 'false' );
			if ( this.target ) {
				this.target.learnExistingRecord( results );
			}
			this.results = results;
			this.renderResults();
			this.updateSize();
			if ( results.length ) {
				this.setStatus( results.length + ( results.length === 1 ? ' Erenshor link found.' :
					' Erenshor links found.' ), false );
			} else {
				this.setStatus( 'No Erenshor links found.', false );
			}
		};

		SemanticLinkDialog.prototype.failSearch = function ( serial ) {
			if ( serial !== this.requestSerial ) {
				return;
			}
			this.clearResults();
			this.$results.attr( 'aria-busy', 'false' );
			this.setStatus( FAILURE_TEXT, true );
		};

		SemanticLinkDialog.prototype.clearSearchTimer = function () {
			if ( this.searchTimer !== null ) {
				window.clearTimeout( this.searchTimer );
				this.searchTimer = null;
			}
		};

		SemanticLinkDialog.prototype.clearResults = function () {
			this.results = [];
			this.activeIndex = -1;
			this.selectedIndex = -1;
			this.selectedResult = null;
			if ( this.$results ) {
				this.$results.empty().attr( 'aria-busy', 'false' );
			}
			if ( this.searchInput ) {
				this.searchInput.$input.removeAttr( 'aria-activedescendant' ).attr( 'aria-expanded', 'false' );
			}
			if ( this.labelField ) {
				this.labelField.$element.hide();
			}
			if ( this.actions ) {
				this.actions.setAbilities( { submit: false } );
			}
		};

		SemanticLinkDialog.prototype.renderResults = function () {
			this.$results.empty();
			this.results.forEach( function ( result, index ) {
				const optionId = this.resultListId + '-option-' + index;
				const detail = result.subtype ? displayKind( result.kind ) + ' · ' + result.subtype :
					displayKind( result.kind );
				const $option = jQuery( '<div>' ).addClass( 'semantic-link-picker__result' ).attr( {
					id: optionId,
					role: 'option',
					'aria-selected': 'false',
					tabindex: '-1',
					'data-erenshor-key': result.key,
					'data-erenshor-kind': result.kind,
					'aria-label': result.name + ', ' + detail + ', ' + result.page + ', ' + result.key
				} );
				const $heading = jQuery( '<div>' ).addClass( 'semantic-link-picker__result-heading' );
				$heading.append(
					jQuery( '<span>' ).addClass( 'semantic-link-picker__result-name' ).text( result.name ),
					jQuery( '<span>' ).addClass( 'semantic-link-picker__result-detail' ).text( detail )
				);
				$option.append( $heading );
				if ( result.page !== result.name ) {
					$option.append(
						jQuery( '<div>' ).addClass( 'semantic-link-picker__result-page' )
							.append( jQuery( '<span>' ).text( 'Page: ' ), jQuery( '<span>' ).text( result.page ) )
					);
				}
				$option.append( jQuery( '<code>' ).addClass( 'semantic-link-picker__result-key' ).text( result.key ) );
				$option.on( 'mouseenter', function () {
					this.setActiveIndex( index );
				}.bind( this ) );
				$option.on( 'mousedown', function ( event ) {
					event.preventDefault();
				} );
				$option.on( 'click', function () {
					this.commitResult( index );
					this.searchInput.focus();
				}.bind( this ) );
				this.$results.append( $option );
			}.bind( this ) );
			this.searchInput.$input.attr( 'aria-expanded', this.results.length ? 'true' : 'false' );
		};

		SemanticLinkDialog.prototype.onSearchKeyDown = function ( event ) {
			if ( event.key === 'ArrowDown' || event.key === 'ArrowUp' ) {
				const index = nextActiveIndex( this.activeIndex, this.results.length, event.key );
				if ( index === -1 ) {
					return;
				}
				event.preventDefault();
				this.setActiveIndex( index );
				return;
			}
			if ( event.key === 'Enter' && this.activeIndex !== -1 ) {
				event.preventDefault();
				this.commitResult( this.activeIndex );
				return;
			}
			if ( event.key === 'Escape' ) {
				event.preventDefault();
				this.close( { action: 'cancel' } );
			}
		};

		SemanticLinkDialog.prototype.setActiveIndex = function ( index ) {
			this.activeIndex = index;
			const $options = this.$results.children( '[role="option"]' );
			$options.removeClass( 'semantic-link-picker__result--active' );
			const $active = $options.eq( index ).addClass( 'semantic-link-picker__result--active' );
			this.searchInput.$input.attr( 'aria-activedescendant', $active.attr( 'id' ) );
			$active[ 0 ].scrollIntoView( { block: 'nearest' } );
		};

		SemanticLinkDialog.prototype.commitResult = function ( index ) {
			const candidate = this.results[ index ];
			if ( this.target ) {
				this.target.resolveLabelForResult( candidate );
			}
			const transition = selectionTransition(
				this.results,
				index,
				this.labelUserEdited,
				this.target ? this.target.customLabel : null
			);
			this.selectedIndex = transition.selectedIndex;
			this.selectedResult = transition.selectedResult;
			this.setActiveIndex( transition.selectedIndex );
			const $options = this.$results.children( '[role="option"]' );
			$options.attr( 'aria-selected', 'false' ).removeClass( 'semantic-link-picker__result--selected' );
			$options.eq( index ).attr( 'aria-selected', 'true' )
				.addClass( 'semantic-link-picker__result--selected' );
			if ( transition.label !== null ) {
				this.setLabelValue( transition.label );
			}
			this.labelField.$element.show();
			this.actions.setAbilities( { submit: true } );
			this.updateSize();
		};

		SemanticLinkDialog.prototype.setStatus = function ( text, error ) {
			this.$status.text( text ).toggleClass( 'semantic-link-picker__status--error', error );
		};

		windowManager = new OO.ui.WindowManager();
		pickerDialog = new SemanticLinkDialog();
		document.body.appendChild( windowManager.$element[ 0 ] );
		windowManager.addWindows( [ pickerDialog ] );
	}
}() );
