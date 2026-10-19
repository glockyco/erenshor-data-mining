/**
 * Draws the graph of Template:Progression graph from the JSON that
 * Module:Erenshor/Progression puts into its container. The text route stays
 * visible until the drawing is complete, and any failure removes the drawing
 * and shows the text again.
 */
( function () {
	'use strict';

	const core = window.ErenshorProgressionGraphCore;
	const SELECTOR = '.erenshor-progression-graph[data-erenshor-progression]';
	const SPACING = { left: 16, top: 40, nodeWidth: 216, columnGap: 136, rowGap: 14 };
	// Lines meet a step at the height of its name.
	const ANCHOR = 30;
	const JUNCTION_GAP = 30;
	const SWEEPS = 8;
	const SEARCH_LIMIT = 12;
	const ZOOM_MIN = 0.25;
	const ZOOM_MAX = 2;
	const ZOOM_STEP = 1.25;
	const SVG = 'http://www.w3.org/2000/svg';
	const MODES = [
		[ 'route', 'The whole route' ],
		[ 'needs', 'What it needs' ],
		[ 'unlocks', 'What it unlocks' ]
	];
	const FILTER_LABELS = { all: 'Every step', quests: 'Quests only', areas: 'Areas only' };
	let instances = 0;

	function element( tag, className, text ) {
		const node = document.createElement( tag );
		if ( className ) {
			node.className = className;
		}
		if ( text !== undefined && text !== null ) {
			node.textContent = text;
		}
		return node;
	}

	function svgElement( tag, attributes ) {
		const node = document.createElementNS( SVG, tag );
		Object.keys( attributes || {} ).forEach( function ( name ) {
			node.setAttribute( name, attributes[ name ] );
		} );
		return node;
	}

	function button( className, text ) {
		const node = element( 'button', className, text );
		node.type = 'button';
		return node;
	}

	function createExplorer( container, model, text ) {
		const id = 'erenshor-progression-graph-' + ( ++instances );
		const base = core.overview( model, model.targets );
		const targets = new Set( model.targets );
		const state = { focus: null, mode: 'route', filter: 'all', zoom: 1, current: base.keys[ base.keys.length - 1 ] };
		const history = [];
		const entries = new Map();
		const expanded = new Set();
		// The first mention of each step in an expanded detail.
		const mentions = new Map();
		const observer = typeof window.ResizeObserver === 'function' ?
			new window.ResizeObserver( function () {
				schedule();
			} ) :
			null;
		let forest = null;
		let view = null;
		let columns = null;
		let layout = null;
		let frame = 0;
		let drag = null;
		let broken = false;
		let matches = [];
		let active = -1;

		function name( key ) {
			return core.stepName( model.record( key ) );
		}

		function destroy() {
			broken = true;
			if ( observer ) {
				observer.disconnect();
			}
			if ( frame ) {
				window.cancelAnimationFrame( frame );
			}
			if ( root.parentNode ) {
				root.parentNode.removeChild( root );
			}
			if ( text ) {
				text.hidden = false;
			}
		}

		function guard( action ) {
			return function () {
				if ( broken ) {
					return undefined;
				}
				try {
					return action.apply( this, arguments );
				} catch ( error ) {
					destroy();
					mw.log.error( error );
					return undefined;
				}
			};
		}

		// ---- controls ----

		const root = element( 'div', 'epg' );
		const controls = element( 'div', 'epg-controls' );
		controls.setAttribute( 'role', 'group' );
		controls.setAttribute( 'aria-label', 'Graph controls' );

		const searchBox = element( 'div', 'epg-search' );
		const searchLabel = element( 'label', null, 'Find a step' );
		const input = element( 'input', 'epg-search-input' );
		input.type = 'search';
		input.id = id + '-search';
		input.autocomplete = 'off';
		input.spellcheck = false;
		input.setAttribute( 'role', 'combobox' );
		input.setAttribute( 'aria-autocomplete', 'list' );
		input.setAttribute( 'aria-expanded', 'false' );
		input.setAttribute( 'aria-controls', id + '-results' );
		searchLabel.htmlFor = input.id;
		const results = element( 'ul', 'epg-results' );
		results.id = id + '-results';
		results.hidden = true;
		results.setAttribute( 'role', 'listbox' );
		results.setAttribute( 'aria-label', 'Matching steps' );
		searchBox.appendChild( searchLabel );
		searchBox.appendChild( input );
		searchBox.appendChild( results );

		const modeGroup = element( 'fieldset', 'epg-modes' );
		modeGroup.appendChild( element( 'legend', null, 'Show' ) );
		const modeInputs = {};
		MODES.forEach( function ( mode ) {
			const label = element( 'label', 'epg-mode' );
			const radio = element( 'input' );
			radio.type = 'radio';
			radio.name = id + '-mode';
			radio.value = mode[ 0 ];
			radio.addEventListener( 'change', guard( function () {
				if ( radio.checked ) {
					setMode( mode[ 0 ] );
				}
			} ) );
			label.appendChild( radio );
			label.appendChild( document.createTextNode( ' ' + mode[ 1 ] ) );
			modeGroup.appendChild( label );
			modeInputs[ mode[ 0 ] ] = radio;
		} );

		const filterLabel = element( 'label', 'epg-filter', 'Steps ' );
		const filterSelect = element( 'select' );
		filterSelect.id = id + '-filter';
		filterLabel.htmlFor = filterSelect.id;
		core.FILTERS.forEach( function ( filter ) {
			const option = element( 'option', null, FILTER_LABELS[ filter ] );
			option.value = filter;
			filterSelect.appendChild( option );
		} );
		filterLabel.appendChild( filterSelect );
		filterSelect.addEventListener( 'change', guard( function () {
			setFilter( filterSelect.value );
		} ) );

		const actions = element( 'div', 'epg-actions' );
		const backButton = button( 'epg-back', 'Back' );
		const resetButton = button( 'epg-reset', 'Reset' );
		resetButton.setAttribute( 'aria-label', 'Reset to the whole route' );
		const zoomOut = button( 'epg-zoom', '-' );
		zoomOut.setAttribute( 'aria-label', 'Zoom out' );
		const zoomIn = button( 'epg-zoom', '+' );
		zoomIn.setAttribute( 'aria-label', 'Zoom in' );
		const fitButton = button( 'epg-fit', 'Fit' );
		fitButton.setAttribute( 'aria-label', 'Fit the graph into view' );
		[ backButton, resetButton, zoomOut, zoomIn, fitButton ].forEach( function ( control ) {
			actions.appendChild( control );
		} );
		let textToggle = null;
		if ( text ) {
			if ( !text.id ) {
				text.id = id + '-text';
			}
			textToggle = button( 'epg-text-toggle', 'Show the route as text' );
			textToggle.setAttribute( 'aria-controls', text.id );
			textToggle.setAttribute( 'aria-expanded', 'true' );
			actions.appendChild( textToggle );
		}

		[ searchBox, modeGroup, filterLabel, actions ].forEach( function ( control ) {
			controls.appendChild( control );
		} );

		const legend = element( 'p', 'epg-legend', 'Each column is a playthrough tier. A line runs from a requirement ' +
			'to the step that needs it on its first way, and a dot gathers requirements that are all needed. ' +
			'A step\'s Ways list its other ways and sources. With a filter, a dashed line stands for the steps ' +
			'that it hides.' );
		legend.id = id + '-legend';

		const body = element( 'div', 'epg-body' );
		const viewport = element( 'div', 'epg-viewport' );
		viewport.setAttribute( 'role', 'group' );
		viewport.setAttribute( 'aria-label', 'Progression graph. The arrow keys move between steps, ' +
			'Enter selects a step, and Escape clears the selection.' );
		viewport.setAttribute( 'aria-describedby', legend.id );
		const sizer = element( 'div', 'epg-sizer' );
		const world = element( 'div', 'epg-world' );
		const lines = svgElement( 'svg', { 'class': 'epg-lines', 'aria-hidden': 'true', focusable: 'false' } );
		const headings = element( 'div', 'epg-headings' );
		headings.setAttribute( 'aria-hidden', 'true' );
		world.appendChild( lines );
		world.appendChild( headings );
		sizer.appendChild( world );
		viewport.appendChild( sizer );
		const panel = element( 'section', 'epg-panel' );
		panel.setAttribute( 'aria-label', 'Selected step' );
		body.appendChild( viewport );
		body.appendChild( panel );
		const status = element( 'p', 'epg-status' );
		status.setAttribute( 'role', 'status' );

		[ controls, legend, body, status ].forEach( function ( part ) {
			root.appendChild( part );
		} );

		// ---- search ----

		function markActive() {
			Array.prototype.forEach.call( results.children, function ( option, index ) {
				option.setAttribute( 'aria-selected', index === active ? 'true' : 'false' );
			} );
			if ( active >= 0 ) {
				input.setAttribute( 'aria-activedescendant', id + '-result-' + active );
				results.children[ active ].scrollIntoView( { block: 'nearest' } );
			} else {
				input.removeAttribute( 'aria-activedescendant' );
			}
		}

		function closeMatches() {
			results.hidden = true;
			input.setAttribute( 'aria-expanded', 'false' );
			input.removeAttribute( 'aria-activedescendant' );
		}

		function showMatches() {
			matches = core.search( model, input.value, SEARCH_LIMIT );
			active = matches.length ? 0 : -1;
			results.textContent = '';
			matches.forEach( function ( match, index ) {
				const option = element( 'li', 'epg-result' );
				option.id = id + '-result-' + index;
				option.setAttribute( 'role', 'option' );
				option.appendChild( element( 'span', 'epg-result-name', match.name ) );
				option.appendChild( element( 'span', 'epg-result-meta', core.kindLabel( match.kind ) + ', ' +
					( match.tier === null ? 'no tier' : 'tier ' + match.tier ) ) );
				option.addEventListener( 'mousedown', function ( event ) {
					event.preventDefault();
				} );
				option.addEventListener( 'click', guard( function () {
					choose( index );
				} ) );
				results.appendChild( option );
			} );
			if ( matches.length ) {
				results.hidden = false;
				input.setAttribute( 'aria-expanded', 'true' );
				markActive();
			} else {
				closeMatches();
				if ( input.value.trim() ) {
					status.textContent = 'No step has that name.';
				}
			}
		}

		function choose( index ) {
			const match = matches[ index ];
			if ( !match ) {
				return;
			}
			closeMatches();
			input.value = match.name;
			go( match.key );
		}

		input.addEventListener( 'input', guard( showMatches ) );
		input.addEventListener( 'keydown', guard( function ( event ) {
			if ( event.key === 'ArrowDown' || event.key === 'ArrowUp' ) {
				event.preventDefault();
				if ( results.hidden ) {
					showMatches();
				} else if ( matches.length ) {
					active = ( active + ( event.key === 'ArrowDown' ? 1 : -1 ) + matches.length ) % matches.length;
					markActive();
				}
			} else if ( event.key === 'Enter' && !results.hidden && active >= 0 ) {
				event.preventDefault();
				choose( active );
			} else if ( event.key === 'Escape' && !results.hidden ) {
				event.preventDefault();
				closeMatches();
			}
		} ) );
		input.addEventListener( 'blur', function () {
			closeMatches();
		} );

		// ---- details ----

		function treeOf( key ) {
			if ( !forest ) {
				forest = core.detailForest( model, base );
			}
			return forest.trees.get( key );
		}

		function stepLink( key ) {
			const record = model.record( key );
			if ( record.page === null ) {
				return element( 'span', 'epg-step-name', core.stepName( record ) );
			}
			const link = element( 'a', null, core.stepName( record ) );
			link.href = mw.util.getUrl( record.page );
			return link;
		}

		function stepButton( key ) {
			const record = model.record( key );
			const control = button( 'epg-step', core.stepName( record ) );
			control.setAttribute( 'aria-label', core.stepName( record ) + ', ' + core.kindLabel( record.kind ) +
				', ' + core.tierLabel( record.tier ) );
			control.addEventListener( 'click', guard( function () {
				go( key );
			} ) );
			return control;
		}

		function renderWays( tree ) {
			const wrap = element( 'div', 'epg-ways' );
			if ( tree.empty ) {
				wrap.appendChild( element( 'p', null, 'No recorded way.' ) );
				return wrap;
			}
			wrap.appendChild( document.createTextNode( 'Any one of' ) );
			const list = element( 'ul' );
			tree.visible.forEach( function ( way ) {
				list.appendChild( renderWay( way ) );
			} );
			renderGroup( list, tree.sources, 'more sources' );
			renderGroup( list, tree.entrances, 'gate-free entrances' );
			wrap.appendChild( list );
			return wrap;
		}

		function renderGroup( list, ways, label ) {
			if ( !ways.length ) {
				return;
			}
			const item = element( 'li' );
			const group = element( 'details', 'epg-group' );
			group.appendChild( element( 'summary', null, ways.length + ' ' + label ) );
			const inner = element( 'ul' );
			ways.forEach( function ( way ) {
				inner.appendChild( renderWay( way ) );
			} );
			group.appendChild( inner );
			item.appendChild( group );
			list.appendChild( item );
		}

		function renderWay( way ) {
			const item = element( 'li', 'epg-way', 'All of' + ( way.first ? ' (first way)' : '' ) );
			if ( !way.needs.length ) {
				item.appendChild( document.createTextNode( ': no further requirements.' ) );
				return item;
			}
			const list = element( 'ul' );
			way.needs.forEach( function ( need ) {
				list.appendChild( renderNeed( need ) );
			} );
			item.appendChild( list );
			return item;
		}

		function renderNeed( tree ) {
			const item = element( 'li' );
			const words = core.needWording( model, tree.need );
			item.appendChild( document.createTextNode( words.lead ) );
			if ( words.key ) {
				item.appendChild( stepLink( words.key ) );
			}
			if ( words.trail ) {
				item.appendChild( document.createTextNode( words.trail ) );
			}
			if ( tree.state === 'reference' ) {
				item.appendChild( document.createTextNode( ' (' ) );
				const jump = button( 'epg-go', base.deps.has( tree.key ) ? 'show step' : 'see its first mention' );
				jump.addEventListener( 'click', guard( function () {
					go( tree.key );
				} ) );
				item.appendChild( jump );
				item.appendChild( document.createTextNode( ')' ) );
			} else if ( tree.state === 'limit' ) {
				item.className = 'epg-depth-limit';
				item.appendChild( document.createTextNode( ' (depth limit reached)' ) );
			} else if ( tree.state === 'expanded' ) {
				item.appendChild( renderWays( tree.ways ) );
			}
			if ( tree.key && ( tree.state === 'expanded' || !mentions.has( tree.key ) ) ) {
				mentions.set( tree.key, item );
			}
			return item;
		}

		function setExpanded( key, open ) {
			const entry = entryFor( key );
			if ( open && !entry.filled ) {
				entry.detail.appendChild( renderWays( treeOf( key ) ) );
				entry.filled = true;
			}
			if ( open ) {
				expanded.add( key );
			} else {
				expanded.delete( key );
			}
			entry.detail.hidden = !open;
			entry.toggle.setAttribute( 'aria-expanded', open ? 'true' : 'false' );
			entry.box.classList.toggle( 'epg-node-open', open );
			if ( key === state.focus ) {
				renderPanel();
			}
			relayout();
		}

		// ---- nodes and layout ----

		function entryFor( key ) {
			let entry = entries.get( key );
			if ( entry ) {
				return entry;
			}
			const record = model.record( key );
			const target = targets.has( key );
			const kind = core.kindLabel( record.kind ) + ( target ? ', target' : '' );
			const box = element( 'div', 'epg-node epg-kind-' + record.kind.replace( /[^a-z0-9_-]/gi, '' ) );
			box.setAttribute( 'data-key', key );
			const select = button( 'epg-node-select' );
			select.tabIndex = -1;
			select.setAttribute( 'aria-label', kind + ': ' + core.stepName( record ) + '. ' + core.tierLabel( record.tier ) + '.' );
			select.appendChild( element( 'span', 'epg-node-kind', kind ) );
			select.appendChild( element( 'span', 'epg-node-name', core.stepName( record ) ) );
			select.appendChild( element( 'span', 'epg-node-tier', record.tier === null ? 'No tier' : 'Tier ' + record.tier ) );
			select.addEventListener( 'click', guard( function () {
				focusStep( key, true );
			} ) );
			select.addEventListener( 'keydown', guard( function ( event ) {
				moveFrom( key, event );
			} ) );
			select.addEventListener( 'focus', guard( function () {
				setCurrent( key );
			} ) );
			const toggle = button( 'epg-node-toggle', 'Ways' );
			toggle.tabIndex = -1;
			toggle.setAttribute( 'aria-expanded', 'false' );
			toggle.setAttribute( 'aria-label', 'Ways and sources of ' + core.stepName( record ) );
			const detail = element( 'div', 'epg-node-detail' );
			detail.id = id + '-detail-' + entries.size;
			detail.hidden = true;
			toggle.setAttribute( 'aria-controls', detail.id );
			toggle.addEventListener( 'click', guard( function () {
				setExpanded( key, !expanded.has( key ) );
			} ) );
			box.appendChild( select );
			box.appendChild( toggle );
			box.appendChild( detail );
			entry = { box: box, select: select, toggle: toggle, detail: detail, filled: false };
			entries.set( key, entry );
			if ( observer ) {
				observer.observe( box );
			}
			return entry;
		}

		function drawNodes() {
			const shown = new Set( view.keys );
			entries.forEach( function ( entry, key ) {
				if ( !shown.has( key ) && entry.box.parentNode ) {
					entry.box.parentNode.removeChild( entry.box );
				}
			} );
			const related = new Set();
			if ( state.focus !== null ) {
				view.deps.get( state.focus ).concat( view.dependents.get( state.focus ) ).forEach( function ( key ) {
					related.add( key );
				} );
			}
			view.keys.forEach( function ( key ) {
				const entry = entryFor( key );
				if ( entry.box.parentNode !== world ) {
					world.appendChild( entry.box );
				}
				entry.select.tabIndex = key === state.current ? 0 : -1;
				entry.box.classList.toggle( 'epg-node-focus', key === state.focus );
				entry.box.classList.toggle( 'epg-node-related', related.has( key ) );
				entry.box.classList.toggle( 'epg-node-target', targets.has( key ) );
				if ( key === state.focus ) {
					entry.select.setAttribute( 'aria-current', 'true' );
				} else {
					entry.select.removeAttribute( 'aria-current' );
				}
			} );
		}

		function hiddenSummary( hidden ) {
			return core.hiddenStepsLabel( hidden.length ) + ': ' + hidden.map( name ).join( ', ' );
		}

		function drawLines() {
			lines.textContent = '';
			lines.setAttribute( 'width', layout.width );
			lines.setAttribute( 'height', layout.height );
			lines.setAttribute( 'viewBox', '0 0 ' + layout.width + ' ' + layout.height );
			const drawn = core.edgeRoutes( view, layout.positions, {
				anchor: ANCHOR,
				junctionGap: JUNCTION_GAP,
				// Between the source and the junctions before the next column.
				labelOffset: ( SPACING.columnGap - JUNCTION_GAP ) / 2,
				labelSpacing: 13
			} );
			drawn.routes.forEach( function ( route ) {
				const classes = [ 'epg-line' ];
				if ( !route.direct ) {
					classes.push( 'epg-line-skip' );
				}
				if ( state.focus !== null && ( route.to === state.focus || route.from === state.focus ) ) {
					classes.push( 'epg-line-focus' );
				}
				const path = svgElement( 'path', { d: route.d, 'class': classes.join( ' ' ) } );
				lines.appendChild( path );
				if ( route.hidden.length ) {
					const title = svgElement( 'title' );
					title.textContent = hiddenSummary( route.hidden );
					path.appendChild( title );
					const label = svgElement( 'text', {
						x: route.label.x,
						y: route.label.y,
						'class': 'epg-line-label',
						'text-anchor': 'middle'
					} );
					label.textContent = core.hiddenStepsLabel( route.hidden.length );
					lines.appendChild( label );
				}
			} );
			drawn.junctions.forEach( function ( junction ) {
				const focused = junction.key === state.focus;
				lines.appendChild( svgElement( 'circle', {
					cx: junction.x,
					cy: junction.y,
					r: 5,
					'class': 'epg-junction' + ( focused ? ' epg-junction-focus' : '' )
				} ) );
				const label = svgElement( 'text', {
					x: junction.x,
					y: junction.y - 10,
					'class': 'epg-junction-label',
					'text-anchor': 'middle'
				} );
				label.textContent = 'all of';
				lines.appendChild( label );
			} );
		}

		function drawHeadings() {
			headings.textContent = '';
			columns.forEach( function ( column, index ) {
				const heading = element( 'div', 'epg-heading',
					column.tier === null ? 'No playthrough tier' : 'Playthrough tier ' + column.tier );
				heading.style.left = ( SPACING.left + index * ( SPACING.nodeWidth + SPACING.columnGap ) ) + 'px';
				heading.style.width = SPACING.nodeWidth + 'px';
				headings.appendChild( heading );
			} );
		}

		function applyZoom() {
			world.style.transform = 'scale(' + state.zoom + ')';
			sizer.style.width = Math.ceil( layout.width * state.zoom ) + 'px';
			sizer.style.height = Math.ceil( layout.height * state.zoom ) + 'px';
		}

		function relayout() {
			if ( !view ) {
				return;
			}
			layout = core.placeColumns( columns, function ( key ) {
				return entries.get( key ).box.offsetHeight;
			}, SPACING );
			layout.positions.forEach( function ( place, key ) {
				const box = entries.get( key ).box;
				box.style.left = place.x + 'px';
				box.style.top = place.y + 'px';
			} );
			world.style.width = layout.width + 'px';
			world.style.height = layout.height + 'px';
			drawLines();
			drawHeadings();
			applyZoom();
		}

		function schedule() {
			if ( frame || broken ) {
				return;
			}
			frame = window.requestAnimationFrame( guard( function () {
				frame = 0;
				relayout();
			} ) );
		}

		function reveal( key, moveFocus ) {
			const place = layout && layout.positions.get( key );
			if ( !place ) {
				return;
			}
			const zoom = state.zoom;
			const left = place.x * zoom;
			const top = place.y * zoom;
			const width = place.width * zoom;
			const height = Math.min( place.height * zoom, viewport.clientHeight );
			if ( left < viewport.scrollLeft || left + width > viewport.scrollLeft + viewport.clientWidth ) {
				viewport.scrollLeft = Math.max( 0, left - ( viewport.clientWidth - width ) / 2 );
			}
			if ( top < viewport.scrollTop || top + height > viewport.scrollTop + viewport.clientHeight ) {
				viewport.scrollTop = Math.max( 0, top - ( viewport.clientHeight - height ) / 2 );
			}
			if ( moveFocus ) {
				entries.get( key ).select.focus( { preventScroll: true } );
			}
		}

		function zoomTo( value, point ) {
			const next = Math.min( ZOOM_MAX, Math.max( ZOOM_MIN, value ) );
			const anchor = point || { x: viewport.clientWidth / 2, y: viewport.clientHeight / 2 };
			const x = ( viewport.scrollLeft + anchor.x ) / state.zoom;
			const y = ( viewport.scrollTop + anchor.y ) / state.zoom;
			state.zoom = next;
			applyZoom();
			viewport.scrollLeft = x * next - anchor.x;
			viewport.scrollTop = y * next - anchor.y;
			syncControls();
		}

		function fit() {
			zoomTo( Math.min( 1, ( viewport.clientWidth - 8 ) / layout.width, ( viewport.clientHeight - 8 ) / layout.height ) );
			viewport.scrollLeft = 0;
			viewport.scrollTop = 0;
		}

		// ---- panel and status ----

		function edgeOf( from, to ) {
			return view.edges.filter( function ( edge ) {
				return edge.from === from && edge.to === to;
			} )[ 0 ] || null;
		}

		function renderSection( heading, keys, edgeFor, empty ) {
			panel.appendChild( element( 'h4', null, heading ) );
			if ( !keys.length ) {
				panel.appendChild( element( 'p', null, empty ) );
				return;
			}
			const list = element( 'ul', 'epg-panel-list' );
			keys.forEach( function ( other ) {
				const item = element( 'li' );
				item.appendChild( stepButton( other ) );
				const edge = edgeFor( other );
				if ( edge && edge.hidden.length ) {
					item.appendChild( document.createTextNode( ', through ' + hiddenSummary( edge.hidden ) ) );
				}
				list.appendChild( item );
			} );
			panel.appendChild( list );
		}

		function renderPanel() {
			panel.textContent = '';
			if ( state.focus === null ) {
				panel.appendChild( element( 'h3', 'epg-panel-title', model.targets.length > 1 ?
					'Routes to ' + model.targets.length + ' targets' :
					'Route to ' + name( model.targets[ 0 ] ) ) );
				panel.appendChild( element( 'p', null, 'Select a step to see what it needs and what it unlocks.' ) );
				const list = element( 'ul', 'epg-panel-list' );
				model.targets.forEach( function ( key ) {
					const item = element( 'li' );
					item.appendChild( stepButton( key ) );
					list.appendChild( item );
				} );
				panel.appendChild( list );
				return;
			}
			const key = state.focus;
			const record = model.record( key );
			const title = element( 'h3', 'epg-panel-title' );
			title.appendChild( stepLink( key ) );
			panel.appendChild( title );
			panel.appendChild( element( 'p', 'epg-panel-meta', core.kindLabel( record.kind ) + '. ' +
				core.tierLabel( record.tier ) + '.' ) );
			const open = expanded.has( key );
			const toggle = button( 'epg-panel-toggle', open ? 'Hide its ways and sources' : 'Show its ways and sources' );
			toggle.setAttribute( 'aria-expanded', open ? 'true' : 'false' );
			toggle.setAttribute( 'aria-controls', entryFor( key ).detail.id );
			toggle.addEventListener( 'click', guard( function () {
				setExpanded( key, !expanded.has( key ) );
				reveal( key, false );
			} ) );
			panel.appendChild( toggle );
			const ways = model.ways( key ).length;
			if ( ways > 1 ) {
				panel.appendChild( element( 'p', null, 'It has ' + ways + ' ways. The graph draws its first way, ' +
					'and its ways and sources list them all.' ) );
			} else if ( !ways ) {
				panel.appendChild( element( 'p', null, 'No recorded way.' ) );
			}
			renderSection( 'Needs', view.deps.get( key ), function ( other ) {
				return edgeOf( other, key );
			}, 'Nothing before it on this route.' );
			renderSection( 'Unlocks', view.dependents.get( key ), function ( other ) {
				return edgeOf( key, other );
			}, 'Nothing after it on this route.' );
		}

		function renderStatus() {
			const count = view.keys.length;
			let words = count === 1 ? '1 step is drawn' : count + ' steps are drawn';
			if ( state.focus !== null && state.mode === 'needs' ) {
				words += ', ' + name( state.focus ) + ' and what it needs';
			} else if ( state.focus !== null && state.mode === 'unlocks' ) {
				words += ', ' + name( state.focus ) + ' and what it unlocks';
			}
			if ( state.filter !== 'all' ) {
				words += '. Only ' + ( state.filter === 'quests' ? 'quests' : 'areas' ) +
					' are drawn, and dashed lines stand for the steps that they hide';
			}
			status.textContent = words + '.';
		}

		function syncControls() {
			MODES.forEach( function ( mode ) {
				const radio = modeInputs[ mode[ 0 ] ];
				radio.checked = state.mode === mode[ 0 ];
				radio.disabled = mode[ 0 ] !== 'route' && state.focus === null;
			} );
			filterSelect.value = state.filter;
			backButton.disabled = !history.length;
			resetButton.disabled = state.focus === null && state.mode === 'route' && state.filter === 'all';
			zoomOut.disabled = state.zoom <= ZOOM_MIN;
			zoomIn.disabled = state.zoom >= ZOOM_MAX;
		}

		// ---- state ----

		function update() {
			let next = base;
			if ( state.focus !== null && state.mode !== 'route' ) {
				next = core.restrict( next, state.focus, state.mode );
			}
			const always = new Set( model.targets );
			if ( state.focus !== null ) {
				always.add( state.focus );
			}
			view = core.filterView( next, model, state.filter, always );
			columns = core.orderColumns( view, model, SWEEPS );
			if ( !view.deps.has( state.current ) ) {
				state.current = state.focus !== null ? state.focus : view.keys[ view.keys.length - 1 ];
			}
			drawNodes();
			relayout();
			renderPanel();
			renderStatus();
			syncControls();
		}

		function remember() {
			history.push( { focus: state.focus, mode: state.mode, filter: state.filter } );
			if ( history.length > 100 ) {
				history.shift();
			}
		}

		function setCurrent( key ) {
			if ( state.current === key ) {
				return;
			}
			const previous = entries.get( state.current );
			if ( previous ) {
				previous.select.tabIndex = -1;
			}
			state.current = key;
			entries.get( key ).select.tabIndex = 0;
		}

		function focusStep( key, moveFocus ) {
			if ( state.focus !== key ) {
				remember();
				state.focus = key;
			}
			state.current = key;
			update();
			reveal( key, moveFocus );
		}

		// A drawn step takes the focus. Another step opens the details of the
		// drawn step that first mentions it.
		function go( key ) {
			if ( base.deps.has( key ) ) {
				focusStep( key, true );
				return;
			}
			treeOf( key );
			const owner = forest.owners.get( key ) || core.routeOwner( model, base, key );
			if ( owner === null ) {
				status.textContent = name( key ) + ' is not on this route.';
				return;
			}
			focusStep( owner, false );
			setExpanded( owner, true );
			const mention = mentions.get( key );
			if ( mention ) {
				mention.tabIndex = -1;
				mention.classList.add( 'epg-mention' );
				reveal( owner, false );
				mention.scrollIntoView( { block: 'nearest' } );
				mention.focus( { preventScroll: true } );
			} else {
				reveal( owner, true );
				status.textContent = name( key ) + ' lies on the route of ' + name( owner ) +
					', beyond the depth that its details show.';
			}
		}

		function setMode( mode ) {
			if ( mode === state.mode || ( mode !== 'route' && state.focus === null ) ) {
				syncControls();
				return;
			}
			remember();
			state.mode = mode;
			update();
			reveal( state.focus !== null ? state.focus : state.current, false );
		}

		function setFilter( filter ) {
			if ( filter === state.filter ) {
				return;
			}
			remember();
			state.filter = filter;
			update();
			reveal( state.focus !== null ? state.focus : state.current, false );
		}

		function moveFrom( key, event ) {
			let next = null;
			if ( event.key === 'Escape' ) {
				if ( state.focus === null ) {
					return;
				}
				event.preventDefault();
				remember();
				state.focus = null;
				state.mode = 'route';
				update();
				reveal( key, true );
				return;
			}
			if ( event.key === 'Home' ) {
				next = columns[ 0 ].keys[ 0 ];
			} else if ( event.key === 'End' ) {
				const last = columns[ columns.length - 1 ].keys;
				next = last[ last.length - 1 ];
			} else {
				const around = core.neighbours( view, columns, key );
				if ( event.key === 'ArrowLeft' ) {
					next = around.needs[ 0 ] || null;
				} else if ( event.key === 'ArrowRight' ) {
					next = around.unlocks[ 0 ] || null;
				} else if ( event.key === 'ArrowUp' ) {
					next = around.up;
				} else if ( event.key === 'ArrowDown' ) {
					next = around.down;
				} else {
					return;
				}
			}
			event.preventDefault();
			if ( next ) {
				setCurrent( next );
				reveal( next, true );
			}
		}

		function setText( visible ) {
			text.hidden = !visible;
			textToggle.setAttribute( 'aria-expanded', visible ? 'true' : 'false' );
			textToggle.textContent = visible ? 'Hide the route as text' : 'Show the route as text';
		}

		backButton.addEventListener( 'click', guard( function () {
			const previous = history.pop();
			if ( !previous ) {
				return;
			}
			state.focus = previous.focus;
			state.mode = previous.mode;
			state.filter = previous.filter;
			update();
			reveal( state.focus !== null ? state.focus : state.current, false );
		} ) );
		resetButton.addEventListener( 'click', guard( function () {
			remember();
			state.focus = null;
			state.mode = 'route';
			state.filter = 'all';
			update();
		} ) );
		zoomOut.addEventListener( 'click', guard( function () {
			zoomTo( state.zoom / ZOOM_STEP );
		} ) );
		zoomIn.addEventListener( 'click', guard( function () {
			zoomTo( state.zoom * ZOOM_STEP );
		} ) );
		fitButton.addEventListener( 'click', guard( fit ) );
		if ( textToggle ) {
			textToggle.addEventListener( 'click', guard( function () {
				setText( text.hidden );
			} ) );
		}

		// Dragging the background pans the graph, and Ctrl with the wheel zooms it.
		viewport.addEventListener( 'pointerdown', guard( function ( event ) {
			if ( event.button !== 0 || event.target.closest( '.epg-node, button, a, input, select, summary' ) ) {
				return;
			}
			drag = { id: event.pointerId, x: event.clientX, y: event.clientY, left: viewport.scrollLeft, top: viewport.scrollTop };
			viewport.setPointerCapture( event.pointerId );
			viewport.classList.add( 'epg-dragging' );
		} ) );
		viewport.addEventListener( 'pointermove', function ( event ) {
			if ( drag && event.pointerId === drag.id ) {
				viewport.scrollLeft = drag.left - ( event.clientX - drag.x );
				viewport.scrollTop = drag.top - ( event.clientY - drag.y );
			}
		} );
		function endDrag( event ) {
			if ( drag && event.pointerId === drag.id ) {
				drag = null;
				viewport.classList.remove( 'epg-dragging' );
			}
		}
		viewport.addEventListener( 'pointerup', endDrag );
		viewport.addEventListener( 'pointercancel', endDrag );
		viewport.addEventListener( 'wheel', guard( function ( event ) {
			if ( !event.ctrlKey ) {
				return;
			}
			event.preventDefault();
			const box = viewport.getBoundingClientRect();
			zoomTo( state.zoom * ( event.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP ),
				{ x: event.clientX - box.left, y: event.clientY - box.top } );
		} ), { passive: false } );

		return {
			draw: function () {
				container.appendChild( root );
				update();
				// The text goes only once the graph has drawn.
				if ( text ) {
					setText( false );
				}
				reveal( state.current, false );
			},
			destroy: destroy
		};
	}

	function initialize( container ) {
		if ( container.hasAttribute( 'data-erenshor-progression-state' ) ) {
			return;
		}
		container.setAttribute( 'data-erenshor-progression-state', 'drawing' );
		let explorer = null;
		try {
			const source = container.querySelector( 'pre.erenshor-progression-data' );
			if ( !source ) {
				throw new Error( 'Progression graph: the container holds no data' );
			}
			const model = core.createModel( core.parsePayload( source.textContent ) );
			const wrapper = container.closest( '.erenshor-progression' );
			const text = wrapper ? wrapper.querySelector( '.erenshor-progression-text' ) : null;
			explorer = createExplorer( container, model, text );
			explorer.draw();
			container.setAttribute( 'data-erenshor-progression-state', 'drawn' );
		} catch ( error ) {
			if ( explorer ) {
				explorer.destroy();
			}
			container.setAttribute( 'data-erenshor-progression-state', 'failed' );
			mw.log.error( error );
		}
	}

	mw.hook( 'wikipage.content' ).add( function ( $content ) {
		$content.find( SELECTOR ).addBack( SELECTOR ).each( function () {
			initialize( this );
		} );
	} );
}() );
