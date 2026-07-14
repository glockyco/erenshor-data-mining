( function () {
	'use strict';

	const ITEM_LINK_SELECTOR = '.erenshor-link--item[data-erenshor-page]';
	const TOOLTIP_ID = 'erenshor-item-tooltip';
	const HOVER_INTENT_DELAY = 300;
	const COARSE_POINTER_QUERY = '(pointer: coarse)';
	const KNOWN_MISSING_CODES = new Set( [ 'invalidtitle', 'missingtitle', 'nosuchpageid' ] );
	const CANONICAL_QUALITIES = [
		'Normal',
		'Improved +1',
		'Improved +2',
		'Improved +3',
		'Improved +4',
		'Improved +5',
		'Blessed',
		'Ascended'
	];
	const QUALITY_TIERS = {
		'Normal': 0,
		'Blessed': 1,
		'Ascended': 2,
		'Improved +1': 3,
		'Improved +2': 4,
		'Improved +3': 5,
		'Improved +4': 6,
		'Improved +5': 7
	};
	const QUALITY_BY_LOWERCASE = CANONICAL_QUALITIES.reduce( function ( values, quality ) {
		values[ quality.toLowerCase() ] = quality;
		return values;
	}, {} );

	mw.loader.using( [ 'mediawiki.api', 'mediawiki.Title' ] ).then( function () {
		if ( document.readyState === 'loading' ) {
			document.addEventListener( 'DOMContentLoaded', initialize, { once: true } );
		} else {
			initialize();
		}
	}, function () {
		// If a required MediaWiki module cannot load, leave ordinary links alone.
	} );

	function canonicalQuality( value ) {
		if ( typeof value !== 'string' ) {
			return null;
		}
		return QUALITY_BY_LOWERCASE[ value.trim().toLowerCase() ] || null;
	}
	function initialize() {
		const api = new mw.Api();
		const cache = new Map();
		const overlay = createOverlay();
		const loadingShell = createLoadingShell();
		const unavailableShell = createUnavailableShell();
		const visualViewport = window.visualViewport;

		let hoverTarget = null;
		let focusTarget = null;
		let focusElement = null;
		let activeTarget = null;
		let activeRequestKey = null;
		let hoverTimer = null;
		let requestSerial = 0;
		let positionFrame = null;
		let describedTarget = null;
		let descriptionTokenAdded = false;

		document.body.appendChild( overlay );
		document.addEventListener( 'pointerover', onPointerOver );
		document.addEventListener( 'pointerout', onPointerOut );
		document.addEventListener( 'focusin', onFocusIn );
		document.addEventListener( 'focusout', onFocusOut );
		document.addEventListener( 'keydown', onKeyDown );
		window.addEventListener( 'scroll', queuePosition, { capture: true, passive: true } );
		window.addEventListener( 'resize', queuePosition, { passive: true } );
		window.addEventListener( 'pagehide', dismissAll );
		window.addEventListener( 'popstate', dismissAll );
		window.addEventListener( 'hashchange', dismissAll );
		if ( visualViewport ) {
			visualViewport.addEventListener( 'scroll', queuePosition, { passive: true } );
			visualViewport.addEventListener( 'resize', queuePosition, { passive: true } );
		}

		function onPointerOver( event ) {
			if ( pointerHoverSuppressed( event ) ) {
				return;
			}

			if ( containsNode( overlay, event.target ) ) {
				return;
			}

			const target = itemLinkFromEvent( event );
			if ( !target || containsNode( target, event.relatedTarget ) ||
				( activeTarget === target && containsNode( overlay, event.relatedTarget ) ) ) {
				return;
			}

			hoverTarget = target;
			clearHoverTimer();
			if ( !focusTarget ) {
				hoverTimer = window.setTimeout( function () {
					hoverTimer = null;
					if ( hoverTarget === target && !focusTarget ) {
						activate( target );
					}
				}, HOVER_INTENT_DELAY );
			}
		}

		function onPointerOut( event ) {
			if ( pointerHoverSuppressed( event ) ) {
				return;
			}

			if ( containsNode( overlay, event.target ) ) {
				if ( containsNode( overlay, event.relatedTarget ) ||
					( activeTarget && containsNode( activeTarget, event.relatedTarget ) ) ) {
					return;
				}
				if ( !focusTarget ) {
					if ( hoverTarget === activeTarget ) {
						hoverTarget = null;
					}
					hideActive();
				}
				return;
			}

			const target = itemLinkFromEvent( event );
			if ( !target || containsNode( target, event.relatedTarget ) ||
				containsNode( overlay, event.relatedTarget ) ) {
				return;
			}

			if ( hoverTarget === target ) {
				hoverTarget = null;
				clearHoverTimer();
			}
			if ( activeTarget === target && focusTarget !== target ) {
				hideActive();
			}
		}

		function onFocusIn( event ) {
			const target = itemLinkFromEvent( event );
			if ( !target ) {
				return;
			}

			focusTarget = target;
			focusElement = event.target instanceof Element ? event.target : null;
			clearHoverTimer();
			activate( target );
		}

		function onFocusOut( event ) {
			const target = itemLinkFromEvent( event );
			if ( !target || containsNode( target, event.relatedTarget ) ) {
				return;
			}

			if ( focusTarget === target ) {
				focusTarget = null;
			}
			focusElement = null;
			removeDescription();

			if ( activeTarget === target && hoverTarget !== target ) {
				hideActive();
			}
			if ( hoverTarget && activeTarget !== hoverTarget ) {
				scheduleHoverActivation( hoverTarget );
			}
		}

		function onKeyDown( event ) {
			if ( event.key === 'Escape' && activeTarget ) {
				hideActive();
				return;
			}
			if ( !activeTarget || !focusTarget ) {
				return;
			}

			const pageStep = Math.max( 1, overlay.clientHeight * 0.8 );
			let delta = 0;
			switch ( event.key ) {
			case 'ArrowDown':
				delta = 40;
				break;
			case 'ArrowUp':
				delta = -40;
				break;
			case 'PageDown':
			case ' ':
				delta = pageStep;
				break;
			case 'PageUp':
				delta = -pageStep;
				break;
			case 'Home':
				overlay.scrollTop = 0;
				event.preventDefault();
				return;
			case 'End':
				overlay.scrollTop = overlay.scrollHeight;
				event.preventDefault();
				return;
			default:
				return;
			}

			if ( typeof overlay.scrollBy === 'function' ) {
				overlay.scrollBy( { top: delta, left: 0, behavior: 'auto' } );
			} else {
				overlay.scrollTop += delta;
			}
			event.preventDefault();
		}

		function scheduleHoverActivation( target ) {
			clearHoverTimer();
			hoverTimer = window.setTimeout( function () {
				hoverTimer = null;
				if ( hoverTarget === target && !focusTarget ) {
					activate( target );
				}
			}, HOVER_INTENT_DELAY );
		}

		function activate( target ) {
			const spec = requestSpec( target );
			if ( !spec ) {
				hideActive();
				return;
			}

			const serial = ++requestSerial;
			activeTarget = target;
			activeRequestKey = spec.cacheKey;
			showLoading();
			if ( focusTarget === target && focusElement ) {
				addDescription( focusElement );
			} else {
				removeDescription();
			}

			loadTooltip( spec ).then( function ( card ) {
				if ( !isCurrent( serial, target, spec.cacheKey ) ) {
					return;
				}
				if ( !target.isConnected ) {
					hideActive();
					return;
				}
				if ( !card ) {
					showUnavailable();
					return;
				}

				const importedPresentation = document.importNode( card, true );
				overlay.replaceChildren( importedPresentation );
				overlay.dataset.state = 'ready';
				positionOverlay();
			}, function () {
				if ( isCurrent( serial, target, spec.cacheKey ) ) {
					showUnavailable();
				}
			} );
		}

		function pointerHoverSuppressed( event ) {
			return event.pointerType === 'touch' ||
				( typeof window.matchMedia === 'function' && window.matchMedia( COARSE_POINTER_QUERY ).matches );
		}
		function requestSpec( target ) {
			// Stable-key resolution stays disabled until generated item data has a production-safe deploy path.
			const title = normalizeTitle( target.dataset.erenshorPage );
			const hasQuality = target.hasAttribute( 'data-erenshor-quality' );
			const quality = hasQuality ?
				canonicalQuality( target.getAttribute( 'data-erenshor-quality' ) ) : 'Normal';
			if ( !title || ( hasQuality && !quality ) ) {
				return null;
			}

			return {
				title: title,
				quality: quality,
				cacheKey: JSON.stringify( [ title, quality ] )
			};
		}

		function loadTooltip( spec ) {
			if ( cache.has( spec.cacheKey ) ) {
				return cache.get( spec.cacheKey );
			}

			const params = {
				action: 'parse',
				prop: 'text',
				format: 'json',
				formatversion: 2,
				disableeditsection: 1,
				disabletoc: 1,
				disablelimitreport: 1,
				page: spec.title
			};

			const request = new Promise( function ( resolve, reject ) {
				api.get( params ).then( function ( response ) {
					try {
						resolve( extractTooltip( response, spec ) );
					} catch ( error ) {
						reject( error );
					}
				}, function ( code ) {
					if ( KNOWN_MISSING_CODES.has( code ) ) {
						resolve( null );
					} else {
						reject( new Error( 'Unable to load item tooltip.' ) );
					}
				} );
			} );

			cache.set( spec.cacheKey, request );
			request.catch( function () {
				if ( cache.get( spec.cacheKey ) === request ) {
					cache.delete( spec.cacheKey );
				}
			} );
			return request;
		}

		function extractTooltip( response, spec ) {
			if ( !response || !response.parse || typeof response.parse.text !== 'string' ) {
				throw new Error( 'Item page response did not contain parsed text.' );
			}

			const parsedDocument = new DOMParser().parseFromString(
				response.parse.text,
				'text/html'
			);
			const cards = Array.from( parsedDocument.querySelectorAll( '.item-tooltip' ) );
			const presentation = selectPresentation( parsedDocument, cards, spec );
			if ( !presentation ) {
				return null;
			}

			const detachedPresentation = presentation.cloneNode( true );
			stripLinks( detachedPresentation );
			normalizeInlineWidths( detachedPresentation );
			return detachedPresentation;
		}

		function selectPresentation( parsedDocument, cards, spec ) {
			const qualitySet = parsedDocument.querySelector( '.item-tooltip-quality-set' );
			if ( qualitySet ) {
				const wrappers = Array.from( qualitySet.querySelectorAll( '.item-tooltip-quality' ) );
				const wrapperQualities = wrappers.map( function ( wrapper ) {
					return canonicalQuality( wrapper.getAttribute( 'data-erenshor-quality' ) );
				} );
				if ( wrapperQualities.some( Boolean ) ) {
					for ( let index = 0; index < wrappers.length; index++ ) {
						if ( wrapperQualities[ index ] === spec.quality ) {
							const card = wrappers[ index ].querySelector( '.item-tooltip' );
							return card ? presentationForCard( card ) : null;
						}
					}
					return null;
				}
			}

			return pageCard( parsedDocument, cards, spec.quality );
		}

		function pageCard( parsedDocument, cards, quality ) {
			if ( !cards.length ) {
				return null;
			}

			const qualityNodes = Array.from( parsedDocument.querySelectorAll( '[data-erenshor-quality]' ) ).filter( function ( node ) {
				return node.classList.contains( 'item-tooltip' ) || node.closest( '.item-tooltip-quality' );
			} );
			if ( qualityNodes.length ) {
				for ( let index = 0; index < qualityNodes.length; index++ ) {
					const node = qualityNodes[ index ];
					if ( canonicalQuality( node.getAttribute( 'data-erenshor-quality' ) ) !== quality ) {
						continue;
					}
					const wrapper = node.closest( '.item-tooltip-quality' );
					if ( wrapper ) {
						const card = wrapper.querySelector( '.item-tooltip' );
						return card ? presentationForCard( card ) : null;
					}
					if ( node.classList.contains( 'item-tooltip' ) ) {
						return presentationForCard( node );
					}
				}
				return null;
			}

			const tier = QUALITY_TIERS[ quality ];
			if ( cards.length === 1 && quality !== 'Normal' && cardTier( cards[ 0 ] ) === tier ) {
				return presentationForCard( cards[ 0 ] );
			}
			if ( cards.length === 1 ) {
				return quality === 'Normal' ? presentationForCard( cards[ 0 ] ) : null;
			}
			for ( let index = 0; index < cards.length; index++ ) {
				if ( cardTier( cards[ index ] ) === tier ) {
					return presentationForCard( cards[ index ] );
				}
			}

			const orderedIndex = CANONICAL_QUALITIES.indexOf( quality );
			return orderedIndex >= 0 && orderedIndex < cards.length ?
				presentationForCard( cards[ orderedIndex ] ) : null;
		}

		function presentationForCard( card ) {
			const fragment = card.ownerDocument.createDocumentFragment();
			fragment.appendChild( card.cloneNode( true ) );
			let sibling = card.nextElementSibling;
			while ( sibling && sibling.matches( '.item-spell-details' ) ) {
				fragment.appendChild( sibling.cloneNode( true ) );
				sibling = sibling.nextElementSibling;
			}
			return fragment;
		}


		function normalizeInlineWidths( root ) {
			const widthSelectors = '.item-tooltip-quality, .item-tooltip, .item-spell-details';
			const elements = [];
			if ( root.nodeType === 1 && root.matches( widthSelectors ) ) {
				elements.push( root );
			}
			if ( typeof root.querySelectorAll === 'function' ) {
				Array.from( root.querySelectorAll( widthSelectors ) ).forEach( function ( element ) {
					elements.push( element );
				} );
			}
			elements.forEach( function ( element ) {
				element.style.removeProperty( 'width' );
				element.style.removeProperty( 'min-width' );
				element.style.removeProperty( 'max-width' );
			} );
		}

		function cardTier( card ) {
			const name = card.querySelector( '.item-tooltip-name' );
			const classes = [];
			if ( name ) {
				Array.from( name.classList ).forEach( function ( className ) {
					classes.push( className );
				} );
			}
			Array.from( card.classList ).forEach( function ( className ) {
				classes.push( className );
			} );
			for ( let index = 0; index < classes.length; index++ ) {
				const match = /^item-tooltip-tier-([0-7])$/.exec( classes[ index ] );
				if ( match ) {
					return Number( match[ 1 ] );
				}
			}
			return null;
		}

		function stripLinks( card ) {
			card.querySelectorAll( 'a' ).forEach( function ( anchor ) {
				const span = card.ownerDocument.createElement( 'span' );
				if ( anchor.className ) {
					span.className = anchor.className;
				}
				while ( anchor.firstChild ) {
					span.appendChild( anchor.firstChild );
				}
				anchor.replaceWith( span );
			} );
		}

		function showLoading() {
			overlay.replaceChildren( loadingShell );
			overlay.dataset.state = 'loading';
			overlay.hidden = false;
			positionOverlay();
		}

		function showUnavailable() {
			overlay.replaceChildren( unavailableShell );
			overlay.dataset.state = 'error';
			overlay.hidden = false;
			positionOverlay();
		}

		function hideActive() {
			requestSerial++;
			activeTarget = null;
			activeRequestKey = null;
			overlay.hidden = true;
			overlay.removeAttribute( 'data-placement' );
			removeDescription();
			if ( positionFrame !== null ) {
				window.cancelAnimationFrame( positionFrame );
				positionFrame = null;
			}
		}

		function dismissAll() {
			clearHoverTimer();
			hoverTarget = null;
			focusTarget = null;
			focusElement = null;
			hideActive();
		}

		function isCurrent( serial, target, cacheKey ) {
			return serial === requestSerial &&
				activeTarget === target &&
				activeRequestKey === cacheKey;
		}

		function addDescription( target ) {
			if ( describedTarget === target ) {
				return;
			}
			removeDescription();

			const tokens = describedByTokens( target );
			descriptionTokenAdded = !tokens.includes( TOOLTIP_ID );
			if ( descriptionTokenAdded ) {
				tokens.push( TOOLTIP_ID );
				target.setAttribute( 'aria-describedby', tokens.join( ' ' ) );
			}
			describedTarget = target;
		}

		function removeDescription( target ) {
			if ( !describedTarget || ( target && describedTarget !== target ) ) {
				return;
			}

			if ( descriptionTokenAdded ) {
				const tokens = describedByTokens( describedTarget ).filter( function ( token ) {
					return token !== TOOLTIP_ID;
				} );
				if ( tokens.length ) {
					describedTarget.setAttribute( 'aria-describedby', tokens.join( ' ' ) );
				} else {
					describedTarget.removeAttribute( 'aria-describedby' );
				}
			}
			describedTarget = null;
			descriptionTokenAdded = false;
		}

		function describedByTokens( target ) {
			return ( target.getAttribute( 'aria-describedby' ) || '' )
				.trim()
				.split( /\s+/ )
				.filter( Boolean );
		}

		function clearHoverTimer() {
			if ( hoverTimer !== null ) {
				window.clearTimeout( hoverTimer );
				hoverTimer = null;
			}
		}

		function queuePosition( event ) {
			if ( event && event.type === 'scroll' && containsNode( overlay, event.target ) ) {
				return;
			}
			if ( overlay.hidden || !activeTarget || positionFrame !== null ) {
				return;
			}
			positionFrame = window.requestAnimationFrame( function () {
				positionFrame = null;
				positionOverlay();
			} );
		}

		function positionOverlay() {
			if ( overlay.hidden || !activeTarget ) {
				return;
			}

			const viewport = viewportBounds( visualViewport );
			const styles = window.getComputedStyle( overlay );
			const gutter = cssPixels( styles.getPropertyValue( '--erenshor-tooltip-viewport-gutter' ) );
			const gap = cssPixels( styles.getPropertyValue( '--erenshor-tooltip-trigger-gap' ) );
			const triggerRect = activeTarget.getBoundingClientRect();

			overlay.style.maxWidth = Math.max( 0, viewport.width - ( gutter * 2 ) ) + 'px';
			let overlayRect = overlay.getBoundingClientRect();
			const naturalHeight = Math.max( overlay.scrollHeight, overlayRect.height );
			const below = triggerRect.bottom + gap;
			const roomBelow = Math.max( 0, viewport.bottom - below - gutter );
			const roomAbove = Math.max( 0, triggerRect.top - viewport.top - gap - gutter );
			const placeBelow = naturalHeight <= roomBelow || roomBelow >= roomAbove;
			const availableHeight = placeBelow ? roomBelow : roomAbove;
			overlay.style.maxHeight = availableHeight + 'px';
			overlayRect = overlay.getBoundingClientRect();

			const minimumLeft = viewport.left + gutter;
			const maximumLeft = viewport.right - gutter - overlayRect.width;
			const centeredLeft = triggerRect.left + ( ( triggerRect.width - overlayRect.width ) / 2 );
			const left = clamp( centeredLeft, minimumLeft, Math.max( minimumLeft, maximumLeft ) );
			const top = placeBelow ? below : triggerRect.top - gap - overlayRect.height;

			overlay.style.left = left + 'px';
			overlay.style.top = top + 'px';
			overlay.dataset.placement = placeBelow ? 'below' : 'above';
		}
	}

	function createOverlay() {
		const overlay = document.createElement( 'div' );
		overlay.id = TOOLTIP_ID;
		overlay.className = 'erenshor-item-tooltip-overlay';
		overlay.setAttribute( 'role', 'tooltip' );
		overlay.hidden = true;
		return overlay;
	}

	function createLoadingShell() {
		const shell = document.createElement( 'div' );
		shell.className = 'item-tooltip erenshor-item-tooltip-loading';
		shell.textContent = 'Loading item…';
		return shell;
	}

	function createUnavailableShell() {
		const shell = document.createElement( 'div' );
		shell.className = 'item-tooltip erenshor-item-tooltip-unavailable';
		shell.textContent = 'Item tooltip unavailable.';
		return shell;
	}

	function itemLinkFromEvent( event ) {
		const eventTarget = event.target instanceof Element ?
			event.target : event.target && event.target.parentElement;
		return eventTarget ? eventTarget.closest( ITEM_LINK_SELECTOR ) : null;
	}

	function containsNode( target, node ) {
		return node instanceof Node && target.contains( node );
	}

	function normalizeTitle( value ) {
		if ( typeof value !== 'string' ) {
			return null;
		}
		try {
			const title = mw.Title.newFromText( value.trim() );
			return title ? title.getPrefixedText() : null;
		} catch ( error ) {
			return null;
		}
	}

	function viewportBounds( visualViewport ) {
		const left = visualViewport ? visualViewport.offsetLeft : 0;
		const top = visualViewport ? visualViewport.offsetTop : 0;
		const width = visualViewport ? visualViewport.width : document.documentElement.clientWidth;
		const height = visualViewport ? visualViewport.height : document.documentElement.clientHeight;
		return {
			left: left,
			top: top,
			width: width,
			height: height,
			right: left + width,
			bottom: top + height
		};
	}

	function cssPixels( value ) {
		const pixels = Number.parseFloat( value );
		return Number.isFinite( pixels ) ? pixels : 0;
	}

	function clamp( value, minimum, maximum ) {
		return Math.min( Math.max( value, minimum ), maximum );
	}
}() );
