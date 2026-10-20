/**
 * Draws the chapter map of Template:Progression graph from the JSON that
 * Module:Erenshor/Progression puts into its container, and adds the view of a
 * step's neighbourhood to the text. The text route stays visible and complete
 * until the map is drawn, and any failure removes what the gadget added.
 */
( function () {
	'use strict';

	const core = window.ErenshorProgressionGraphCore;
	const SELECTOR = '.erenshor-progression-graph[data-erenshor-progression]';
	const CARD = { width: 220, height: 60, gapX: 24, gapY: 34, bend: 12 };
	// The gap between neighbourhood columns holds the labels of the lines.
	const NEAR = { width: 200, height: 44, gapX: 110, gapY: 10 };
	const NEAR_HEAD = 24;
	const ARROW = 8;
	const SEARCH_LIMIT = 12;
	const SVG = 'http://www.w3.org/2000/svg';
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

	function pageLink( page, name ) {
		if ( !page ) {
			return document.createTextNode( name );
		}
		const link = element( 'a', null, name );
		link.href = mw.util.getUrl( page );
		return link;
	}

	function countLabel( count ) {
		return count === 1 ? '1 step' : count + ' steps';
	}

	function scrollBehavior() {
		return window.matchMedia && window.matchMedia( '( prefers-reduced-motion: reduce )' ).matches ?
			'auto' : 'smooth';
	}

	function createMap( container, model ) {
		const id = 'erenshor-progression-map-' + ( ++instances );
		const root = container.closest( '.erenshor-progression' );
		const route = root ? root.querySelector( '.erenshor-progression-route' ) : null;
		if ( !route ) {
			throw new Error( 'Progression graph: the page holds no route' );
		}
		const items = new Map();
		route.querySelectorAll( 'li[data-progression-key]' ).forEach( function ( item ) {
			items.set( item.getAttribute( 'data-progression-key' ), item );
		} );
		model.order.forEach( function ( key ) {
			if ( !items.has( key ) ) {
				throw new Error( 'Progression graph: the text lacks the step ' + key );
			}
		} );
		const chapterBoxes = Array.from( route.querySelectorAll( '.erenshor-progression-chapter' ) );
		if ( chapterBoxes.length !== model.chapters.length ) {
			throw new Error( 'Progression graph: the text and the data disagree about the chapters' );
		}
		const added = [];
		const state = { goal: model.targets[ 0 ], custom: null, visible: null, marked: null, mapOpen: true };

		// ---- controls ----

		const panel = element( 'div', 'epg' );
		panel.id = id;
		const controls = element( 'div', 'epg-controls' );
		const goalLabel = element( 'label', 'epg-goal', 'Route to ' );
		const goalSelect = element( 'select', 'epg-goal-select' );
		model.targets.forEach( function ( key ) {
			const option = element( 'option', null, model.record( key ).name );
			option.value = key;
			goalSelect.appendChild( option );
		} );
		goalLabel.appendChild( goalSelect );
		controls.appendChild( goalLabel );

		const searchBox = element( 'div', 'epg-search' );
		const searchLabel = element( 'label', null, 'Find a step' );
		const searchInput = element( 'input', 'epg-search-input' );
		searchInput.type = 'search';
		searchInput.id = id + '-search';
		searchInput.setAttribute( 'role', 'combobox' );
		searchInput.setAttribute( 'aria-autocomplete', 'list' );
		searchInput.setAttribute( 'aria-expanded', 'false' );
		searchInput.setAttribute( 'aria-controls', id + '-results' );
		searchLabel.htmlFor = searchInput.id;
		const results = element( 'ul', 'epg-results' );
		results.id = id + '-results';
		results.setAttribute( 'role', 'listbox' );
		results.hidden = true;
		searchBox.appendChild( searchLabel );
		searchBox.appendChild( searchInput );
		searchBox.appendChild( results );
		controls.appendChild( searchBox );

		const mapToggle = button( 'epg-map-toggle', 'Hide the map' );
		mapToggle.setAttribute( 'aria-expanded', 'true' );
		mapToggle.setAttribute( 'aria-controls', id + '-map' );
		controls.appendChild( mapToggle );
		panel.appendChild( controls );

		const status = element( 'p', 'epg-status' );
		status.setAttribute( 'aria-live', 'polite' );
		panel.appendChild( status );

		const mapBox = element( 'div', 'epg-map' );
		mapBox.id = id + '-map';
		mapBox.setAttribute( 'role', 'group' );
		mapBox.setAttribute( 'aria-label', 'Chapter map' );
		const lines = svgElement( 'svg', { 'class': 'epg-lines', 'aria-hidden': 'true' } );
		const cards = element( 'div', 'epg-cards' );
		mapBox.appendChild( cards );
		panel.appendChild( mapBox );

		// ---- the text of one goal ----

		function applyGoal() {
			state.visible = core.goalSteps( model, state.goal );
			items.forEach( function ( item, key ) {
				item.hidden = !state.visible.has( key );
			} );
			let count = 0;
			let shownChapters = 0;
			chapterBoxes.forEach( function ( box ) {
				let shown = 0;
				box.querySelectorAll( 'ol.erenshor-progression-steps' ).forEach( function ( list ) {
					const inList = Array.from( list.children ).filter( function ( item ) {
						return !item.hidden;
					} ).length;
					list.start = count + 1;
					list.hidden = inList === 0;
					const title = list.previousElementSibling;
					if ( title && title.classList.contains( 'erenshor-progression-part-title' ) ) {
						title.hidden = inList === 0;
					}
					count += inList;
					shown += inList;
				} );
				box.hidden = shown === 0;
				if ( shown ) {
					shownChapters++;
					const number = box.querySelector( '.erenshor-progression-chapter-number' );
					if ( number ) {
						number.textContent = String( shownChapters );
					}
				}
			} );
			status.textContent = 'Route to ' + model.record( state.goal ).name + ': ' +
				( shownChapters === 1 ? '1 chapter' : shownChapters + ' chapters' ) + ' and ' + countLabel( count ) + '.';
			drawMap();
		}

		function setGoal( key ) {
			state.goal = key;
			if ( model.targets.indexOf( key ) === -1 ) {
				if ( !state.custom ) {
					state.custom = element( 'option' );
					goalSelect.appendChild( state.custom );
				}
				state.custom.value = key;
				state.custom.textContent = model.record( key ).name;
			}
			goalSelect.value = key;
			applyGoal();
		}

		// ---- the chapter map ----

		let mapCards = [];

		function drawMap() {
			const graph = core.chapterGraph( model, state.visible );
			// A route of one chapter has nothing to find on a map.
			const single = graph.chapters.length < 2;
			mapToggle.hidden = single;
			mapBox.hidden = single || !state.mapOpen;
			const layout = core.layoutChapters( graph, CARD );
			lines.textContent = '';
			cards.textContent = '';
			cards.appendChild( lines );
			lines.setAttribute( 'width', layout.width );
			lines.setAttribute( 'height', layout.height );
			lines.setAttribute( 'viewBox', '0 0 ' + layout.width + ' ' + layout.height );
			cards.style.width = layout.width + 'px';
			cards.style.height = layout.height + 'px';
			layout.lines.forEach( function ( line ) {
				lines.appendChild( svgElement( 'path', { d: core.linePath( line.points ), 'class': 'epg-line' } ) );
			} );
			mapCards = layout.cards.map( function ( place, position ) {
				const chapter = graph.chapters[ position ];
				const card = button( 'epg-card' );
				card.style.left = place.x + 'px';
				card.style.top = place.y + 'px';
				card.style.width = place.width + 'px';
				card.style.height = place.height + 'px';
				card.appendChild( element( 'span', 'epg-card-number', String( position + 1 ) ) );
				card.appendChild( element( 'span', 'epg-card-title', chapter.title ) );
				card.title = chapter.title;
				card.appendChild( element( 'span', 'epg-card-count', countLabel( chapter.steps.length ) ) );
				card.setAttribute( 'aria-label', 'Chapter ' + ( position + 1 ) + ', ' + chapter.title + ', ' +
					countLabel( chapter.steps.length ) );
				card.addEventListener( 'click', guard( function () {
					markChapter( chapter.chapter, true );
				} ) );
				cards.appendChild( card );
				return { card: card, chapter: chapter.chapter };
			} );
			markChapter( state.marked, false );
		}

		function markChapter( index, move ) {
			state.marked = index;
			chapterBoxes.forEach( function ( box, position ) {
				box.classList.toggle( 'epg-marked', position === index );
			} );
			mapCards.forEach( function ( entry ) {
				if ( entry.chapter === index ) {
					entry.card.setAttribute( 'aria-current', 'true' );
				} else {
					entry.card.removeAttribute( 'aria-current' );
				}
			} );
			if ( move && index !== null ) {
				chapterBoxes[ index ].scrollIntoView( { behavior: scrollBehavior(), block: 'start' } );
			}
		}

		// ---- the neighbourhood of a step ----

		const views = new Map();

		function nearCard( entry, label, isCenter ) {
			const name = model.record( entry.key ).name;
			const card = button( 'epg-near-card' + ( isCenter ? ' epg-near-center' : '' ) );
			card.appendChild( element( 'span', 'epg-near-name', name ) );
			card.title = name;
			card.setAttribute( 'aria-label', label );
			card.style.left = entry.x + 'px';
			card.style.top = ( entry.y + NEAR_HEAD ) + 'px';
			card.style.width = NEAR.width + 'px';
			card.style.height = NEAR.height + 'px';
			return card;
		}

		function renderNeighbourhood( view, key ) {
			view.box.textContent = '';
			view.current = key;
			const near = core.neighbourhood( model, key );
			const centerName = model.record( key ).name;
			const head = element( 'div', 'epg-near-head' );
			if ( key !== view.step ) {
				head.appendChild( element( 'span', 'epg-near-title', 'Around ' + centerName ) );
				const back = button( 'epg-near-back', 'Back to this step' );
				back.addEventListener( 'click', guard( function () {
					renderNeighbourhood( view, view.step );
				} ) );
				head.appendChild( back );
			} else if ( model.targets.indexOf( key ) === -1 && key !== state.goal ) {
				const focus = button( 'epg-near-goal', 'Show only the route to this step' );
				focus.addEventListener( 'click', guard( function () {
					setGoal( key );
					view.item.scrollIntoView( { behavior: scrollBehavior(), block: 'nearest' } );
				} ) );
				head.appendChild( focus );
			}
			if ( head.childNodes.length ) {
				view.box.appendChild( head );
			}
			if ( near.sentence && key !== view.step ) {
				const sentence = element( 'p', 'epg-near-sentence' );
				core.sentenceParts( model, near.sentence ).forEach( function ( part ) {
					sentence.appendChild( part.text !== undefined ? document.createTextNode( part.text ) :
						pageLink( part.page, part.name ) );
				} );
				view.box.appendChild( sentence );
			}
			if ( !near.needs.length && !near.unlocks.length ) {
				view.box.appendChild( element( 'p', 'epg-near-none', 'Nothing on this route connects to it.' ) );
				return;
			}
			const layout = core.layoutNeighbourhood( near, NEAR );
			const height = layout.height + NEAR_HEAD;
			const frame = element( 'div', 'epg-near-frame' );
			frame.style.width = layout.width + 'px';
			frame.style.height = height + 'px';
			const svg = svgElement( 'svg', { 'class': 'epg-lines', width: layout.width, height: height, 'aria-hidden': 'true' } );
			frame.appendChild( svg );
			function heading( text, x ) {
				const node = element( 'span', 'epg-near-heading', text );
				node.style.left = x + 'px';
				node.style.width = NEAR.width + 'px';
				frame.appendChild( node );
			}
			if ( layout.needs.length ) {
				heading( 'Needs', layout.needs[ 0 ].x );
			}
			if ( layout.unlocks.length ) {
				heading( 'Needed for', layout.unlocks[ 0 ].x );
			}
			function shifted( point ) {
				return { x: point.x, y: point.y + NEAR_HEAD };
			}
			// The label at the fork of a group says what the reader does with the
			// node at the start of its lines.
			layout.groups.forEach( function ( group ) {
				group.paths.forEach( function ( path ) {
					svg.appendChild( svgElement( 'path', { 'class': 'epg-line', d: core.sidewaysPath( shifted( path.from ), shifted( path.to ) ) } ) );
				} );
				const label = element( 'span', 'epg-near-action', group.action );
				label.style.left = group.fork.x + 'px';
				label.style.top = ( group.fork.y + NEAR_HEAD ) + 'px';
				label.setAttribute( 'aria-hidden', 'true' );
				frame.appendChild( label );
			} );
			layout.arrows.forEach( function ( point ) {
				const tip = shifted( point );
				svg.appendChild( svgElement( 'path', {
					'class': 'epg-arrow',
					d: 'M' + ( tip.x - ARROW ) + ' ' + ( tip.y - ARROW / 2 ) + ' L' + tip.x + ' ' + tip.y + ' L' +
						( tip.x - ARROW ) + ' ' + ( tip.y + ARROW / 2 ) + ' Z'
				} ) );
			} );
			function neighbour( entry, label ) {
				const card = nearCard( entry, label + ( model.isStep( entry.key ) ? ', go to its step' : ', show its connections' ), false );
				card.addEventListener( 'click', guard( function () {
					if ( model.isStep( entry.key ) ) {
						openStep( entry.key, true );
					} else {
						renderNeighbourhood( view, entry.key );
					}
				} ) );
				frame.appendChild( card );
			}
			layout.needs.forEach( function ( entry ) {
				neighbour( entry, entry.action + ' ' + model.record( entry.key ).name );
			} );
			layout.unlocks.forEach( function ( entry ) {
				neighbour( entry, entry.action + ' ' + centerName + ' for ' + model.record( entry.key ).name );
			} );
			const center = nearCard( layout.center, centerName, true );
			center.disabled = true;
			frame.appendChild( center );
			view.box.appendChild( frame );
		}

		function viewOf( key ) {
			let view = views.get( key );
			if ( !view ) {
				const item = items.get( key );
				const toggle = button( 'epg-near-toggle', 'Show connections' );
				toggle.setAttribute( 'aria-expanded', 'false' );
				const box = element( 'div', 'epg-near' );
				box.hidden = true;
				box.id = id + '-near-' + views.size;
				toggle.setAttribute( 'aria-controls', box.id );
				const sentence = item.querySelector( '.erenshor-progression-sentence' );
				const after = item.querySelector( '.erenshor-progression-yields' ) || sentence;
				after.parentNode.insertBefore( box, after.nextSibling );
				after.parentNode.insertBefore( toggle, box );
				after.parentNode.insertBefore( document.createTextNode( ' ' ), toggle );
				view = { step: key, item: item, toggle: toggle, box: box, current: null };
				toggle.addEventListener( 'click', guard( function () {
					setOpen( view, view.box.hidden );
				} ) );
				views.set( key, view );
				added.push( toggle, box );
			}
			return view;
		}

		function setOpen( view, open ) {
			if ( open ) {
				renderNeighbourhood( view, view.step );
			}
			view.box.hidden = !open;
			view.toggle.textContent = open ? 'Hide connections' : 'Show connections';
			view.toggle.setAttribute( 'aria-expanded', String( open ) );
		}

		function openStep( key, open ) {
			if ( !state.visible.has( key ) ) {
				const target = model.targets.find( function ( goal ) {
					return core.goalSteps( model, goal ).has( key );
				} );
				setGoal( target || key );
			}
			const view = viewOf( key );
			if ( open ) {
				setOpen( view, true );
			}
			markStep( key );
		}

		function markStep( key ) {
			items.forEach( function ( item ) {
				item.classList.remove( 'epg-marked' );
			} );
			const item = items.get( key );
			item.classList.add( 'epg-marked' );
			item.scrollIntoView( { behavior: scrollBehavior(), block: 'center' } );
			item.tabIndex = -1;
			item.focus( { preventScroll: true } );
		}

		// ---- search ----

		let found = [];
		let active = -1;

		function closeResults() {
			results.hidden = true;
			results.textContent = '';
			searchInput.setAttribute( 'aria-expanded', 'false' );
			searchInput.removeAttribute( 'aria-activedescendant' );
			found = [];
			active = -1;
		}

		function showResults() {
			found = core.search( model, searchInput.value, SEARCH_LIMIT );
			results.textContent = '';
			active = found.length ? 0 : -1;
			found.forEach( function ( entry, index ) {
				const option = element( 'li', 'epg-result' );
				option.id = id + '-result-' + index;
				option.setAttribute( 'role', 'option' );
				option.appendChild( element( 'span', 'epg-result-name', entry.name ) );
				if ( entry.owner !== entry.key ) {
					option.appendChild( element( 'span', 'epg-result-meta', ' in the step of ' + model.record( entry.owner ).name ) );
				}
				option.addEventListener( 'mousedown', function ( event ) {
					event.preventDefault();
				} );
				option.addEventListener( 'click', guard( function () {
					choose( index );
				} ) );
				results.appendChild( option );
			} );
			results.hidden = !found.length;
			searchInput.setAttribute( 'aria-expanded', String( found.length > 0 ) );
			highlight();
		}

		function highlight() {
			Array.from( results.children ).forEach( function ( option, index ) {
				option.setAttribute( 'aria-selected', String( index === active ) );
			} );
			if ( active >= 0 ) {
				searchInput.setAttribute( 'aria-activedescendant', id + '-result-' + active );
			} else {
				searchInput.removeAttribute( 'aria-activedescendant' );
			}
		}

		function choose( index ) {
			const entry = found[ index ];
			if ( !entry ) {
				return;
			}
			closeResults();
			searchInput.value = entry.name;
			openStep( entry.owner, false );
			status.textContent = entry.owner === entry.key ? entry.name + ' is a step of this route.' :
				entry.name + ' is part of the step of ' + model.record( entry.owner ).name + '.';
		}

		// ---- wiring ----

		function guard( handler ) {
			return function ( event ) {
				try {
					return handler( event );
				} catch ( error ) {
					mw.log.error( error );
					destroy();
				}
			};
		}

		goalSelect.addEventListener( 'change', guard( function () {
			setGoal( goalSelect.value );
		} ) );
		searchInput.addEventListener( 'input', guard( showResults ) );
		searchInput.addEventListener( 'keydown', guard( function ( event ) {
			if ( event.key === 'ArrowDown' || event.key === 'ArrowUp' ) {
				if ( found.length ) {
					event.preventDefault();
					active = ( active + ( event.key === 'ArrowDown' ? 1 : found.length - 1 ) ) % found.length;
					highlight();
				}
			} else if ( event.key === 'Enter' ) {
				if ( active >= 0 ) {
					event.preventDefault();
					choose( active );
				}
			} else if ( event.key === 'Escape' ) {
				closeResults();
			}
		} ) );
		searchInput.addEventListener( 'blur', function () {
			setTimeout( closeResults, 150 );
		} );
		mapToggle.addEventListener( 'click', guard( function () {
			state.mapOpen = !state.mapOpen;
			mapBox.hidden = !state.mapOpen;
			mapToggle.textContent = state.mapOpen ? 'Hide the map' : 'Show the map';
			mapToggle.setAttribute( 'aria-expanded', String( state.mapOpen ) );
		} ) );

		function destroy() {
			panel.remove();
			added.forEach( function ( node ) {
				node.remove();
			} );
			items.forEach( function ( item ) {
				item.hidden = false;
				item.classList.remove( 'epg-marked' );
			} );
			chapterBoxes.forEach( function ( box, index ) {
				box.hidden = false;
				box.classList.remove( 'epg-marked' );
				const number = box.querySelector( '.erenshor-progression-chapter-number' );
				if ( number ) {
					number.textContent = String( index + 1 );
				}
			} );
			let count = 0;
			route.querySelectorAll( 'ol.erenshor-progression-steps' ).forEach( function ( list ) {
				list.hidden = false;
				list.start = count + 1;
				count += list.children.length;
				const title = list.previousElementSibling;
				if ( title && title.classList.contains( 'erenshor-progression-part-title' ) ) {
					title.hidden = false;
				}
			} );
			container.setAttribute( 'data-erenshor-progression-state', 'failed' );
		}

		return {
			draw: function () {
				container.appendChild( panel );
				model.order.forEach( viewOf );
				applyGoal();
			},
			destroy: destroy
		};
	}

	function initialize( container ) {
		if ( container.hasAttribute( 'data-erenshor-progression-state' ) ) {
			return;
		}
		container.setAttribute( 'data-erenshor-progression-state', 'drawing' );
		let map = null;
		try {
			const source = container.querySelector( 'pre.erenshor-progression-data' );
			if ( !source ) {
				throw new Error( 'Progression graph: the container holds no data' );
			}
			const model = core.createModel( core.parsePayload( source.textContent ) );
			map = createMap( container, model );
			map.draw();
			container.setAttribute( 'data-erenshor-progression-state', 'drawn' );
		} catch ( error ) {
			if ( map ) {
				map.destroy();
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
