( function ( root, factory ) {
	const core = factory();
	if ( typeof process === 'object' && process.versions && process.versions.node &&
		typeof module === 'object' && module.exports ) {
		module.exports = core;
	} else {
		root.ErenshorProgressionGraphCore = core;
	}
}( typeof self !== 'undefined' ? self : typeof globalThis !== 'undefined' ? globalThis : this, function () {
	'use strict';

	// The positional fields of a packed need, in the order that the header of
	// Module:Erenshor/Data/Progression documents.
	const NEED_FIELDS = [
		'relation', 'need', 'quantity', 'slot', 'keywords', 'text', 'advisory', 'unconfirmed', 'requiredLevel'
	];
	const PLACEHOLDER = /\{([^{}]+)\}/g;
	// A quest's start carries its quest's name and reads as part of the quest.
	const QUEST_START = 'quest_start';

	function fail( message ) {
		throw new Error( 'Progression graph: ' + message );
	}

	function isObject( value ) {
		return value !== null && typeof value === 'object' && !Array.isArray( value );
	}

	function isText( value ) {
		return typeof value === 'string' && value !== '';
	}

	// Lua writes an empty table as an empty object or an empty array.
	function list( value, what ) {
		if ( value === undefined || ( isObject( value ) && !Object.keys( value ).length ) ) {
			return [];
		}
		if ( !Array.isArray( value ) || !value.every( isText ) ) {
			fail( what + ' is not a list of keys' );
		}
		return value.slice();
	}

	function normalizeRecord( key, source ) {
		if ( !isObject( source ) || !isText( source.kind ) || !isText( source.name ) ) {
			fail( 'node ' + key + ' has no kind or name' );
		}
		let page;
		if ( source.page === undefined ) {
			page = source.name;
		} else if ( source.page === false ) {
			page = null;
		} else if ( isText( source.page ) ) {
			page = source.page;
		} else {
			fail( 'node ' + key + ' has an invalid page' );
		}
		if ( source.way !== undefined && typeof source.way !== 'string' ) {
			fail( 'node ' + key + ' has an invalid way' );
		}
		return { key: key, kind: source.kind, name: source.name, page: page, packed: source.way || null };
	}

	/**
	 * Read the payload that Module:Erenshor/Progression renders for the gadget:
	 * the goals, the chapters with their parts and steps in route order, what
	 * each step needs on the route, and the route's nodes with their first ways.
	 */
	function parsePayload( text ) {
		let payload;
		try {
			payload = JSON.parse( text );
		} catch ( error ) {
			fail( 'the data cannot be read: ' + error.message );
		}
		if ( !isObject( payload ) ) {
			fail( 'the data is not a record' );
		}
		const targets = list( payload.targets, 'the targets' );
		if ( !targets.length ) {
			fail( 'the data names no targets' );
		}
		const unmet = new Set( list( payload.unmet, 'the unmet relations' ) );
		if ( !isObject( payload.actions ) || !Object.keys( payload.actions ).every( function ( key ) {
			return isText( payload.actions[ key ] );
		} ) ) {
			fail( 'the data has no actions' );
		}
		if ( !isObject( payload.nodes ) || !isObject( payload.steps ) || !Array.isArray( payload.chapters ) ) {
			fail( 'the data has no route' );
		}
		const records = new Map();
		Object.keys( payload.nodes ).forEach( function ( key ) {
			records.set( key, normalizeRecord( key, payload.nodes[ key ] ) );
		} );
		const steps = new Map();
		const order = [];
		const chapters = payload.chapters.map( function ( chapter, index ) {
			if ( !isObject( chapter ) || !isText( chapter.title ) || !Array.isArray( chapter.parts ) ) {
				fail( 'chapter ' + ( index + 1 ) + ' is malformed' );
			}
			return {
				index: index,
				title: chapter.title,
				parts: chapter.parts.map( function ( part ) {
					if ( !isObject( part ) || !isText( part.title ) ) {
						fail( 'a part of chapter ' + ( index + 1 ) + ' is malformed' );
					}
					const keys = list( part.steps, 'a part of chapter ' + ( index + 1 ) );
					keys.forEach( function ( key ) {
						const source = payload.steps[ key ];
						if ( !isObject( source ) || !records.has( key ) || steps.has( key ) ) {
							fail( 'the step ' + key + ' is missing or repeated' );
						}
						steps.set( key, {
							key: key,
							chapter: index,
							deps: list( source.deps, 'the needs of ' + key ),
							folds: list( source.folds, 'the rewards of ' + key )
						} );
						order.push( key );
					} );
					return { title: part.title, steps: keys };
				} )
			};
		} );
		steps.forEach( function ( step ) {
			step.deps.concat( step.folds ).forEach( function ( key ) {
				if ( !records.has( key ) || ( step.deps.indexOf( key ) !== -1 && !steps.has( key ) ) ) {
					fail( 'the step ' + step.key + ' names ' + key + ', which the route lacks' );
				}
			} );
		} );
		targets.forEach( function ( key ) {
			if ( !steps.has( key ) ) {
				fail( 'the target ' + key + ' is no step' );
			}
		} );
		return {
			targets: targets,
			unmet: unmet,
			actions: payload.actions,
			chapters: chapters,
			steps: steps,
			order: order,
			records: records
		};
	}

	function decodeNeed( owner, values ) {
		if ( !Array.isArray( values ) || !values.length || values.length > NEED_FIELDS.length ) {
			fail( 'node ' + owner + ' has a malformed need' );
		}
		const need = {};
		NEED_FIELDS.forEach( function ( field, index ) {
			need[ field ] = values[ index ] === undefined ? null : values[ index ];
		} );
		if ( !isText( need.relation ) || ( need.need !== null && !isText( need.need ) ) ) {
			fail( 'node ' + owner + ' has a need without a relation or with an invalid step' );
		}
		return need;
	}

	/**
	 * Wrap a parsed payload. A first way is decoded when a caller first reads it.
	 */
	function createModel( payload ) {
		const records = payload.records;
		const decoded = new Map();
		const rank = new Map();
		payload.order.forEach( function ( key, index ) {
			rank.set( key, index );
		} );
		const folded = new Map();
		payload.steps.forEach( function ( step ) {
			step.folds.forEach( function ( key ) {
				folded.set( key, step.key );
			} );
		} );
		let reverse = null;

		function record( key ) {
			const found = records.get( key );
			if ( !found ) {
				fail( 'the data lacks the node ' + key );
			}
			return found;
		}

		function firstWay( key ) {
			if ( decoded.has( key ) ) {
				return decoded.get( key );
			}
			const source = record( key );
			let way = null;
			if ( source.packed ) {
				let values;
				try {
					values = JSON.parse( source.packed );
				} catch ( error ) {
					fail( 'the way of ' + key + ' cannot be read' );
				}
				if ( !Array.isArray( values ) || typeof values[ 0 ] !== 'string' ) {
					fail( 'the way of ' + key + ' has no sentence' );
				}
				way = {
					sentence: values[ 0 ],
					needs: values.slice( 1 ).map( function ( need ) {
						return decodeNeed( key, need );
					} )
				};
			}
			decoded.set( key, way );
			return way;
		}

		// What needs each node on the route: the nodes whose first way names it.
		function users( key ) {
			if ( !reverse ) {
				reverse = new Map();
				Array.from( records.keys() ).forEach( function ( other ) {
					const way = firstWay( other );
					( way ? way.needs : [] ).forEach( function ( need ) {
						if ( need.need && records.has( need.need ) && !payload.unmet.has( need.relation ) ) {
							if ( !reverse.has( need.need ) ) {
								reverse.set( need.need, [] );
							}
							reverse.get( need.need ).push( { key: other, need: need } );
						}
					} );
				} );
			}
			return reverse.get( key ) || [];
		}

		/**
		 * The step that shows a node: the step itself, the quest whose step names
		 * its reward, or the earliest step whose first way leads to it.
		 */
		function owner( key ) {
			if ( payload.steps.has( key ) ) {
				return key;
			}
			if ( folded.has( key ) ) {
				return folded.get( key );
			}
			const seen = new Set( [ key ] );
			let layer = [ key ];
			while ( layer.length ) {
				const next = [];
				const found = [];
				layer.forEach( function ( current ) {
					users( current ).forEach( function ( use ) {
						if ( seen.has( use.key ) ) {
							return;
						}
						seen.add( use.key );
						if ( payload.steps.has( use.key ) || folded.has( use.key ) ) {
							found.push( payload.steps.has( use.key ) ? use.key : folded.get( use.key ) );
						} else {
							next.push( use.key );
						}
					} );
				} );
				if ( found.length ) {
					return found.sort( function ( a, b ) {
						return rank.get( a ) - rank.get( b );
					} )[ 0 ];
				}
				layer = next;
			}
			return null;
		}

		return {
			targets: payload.targets,
			unmet: payload.unmet,
			actions: payload.actions,
			chapters: payload.chapters,
			steps: payload.steps,
			order: payload.order,
			has: function ( key ) {
				return records.has( key );
			},
			isStep: function ( key ) {
				return payload.steps.has( key );
			},
			rank: function ( key ) {
				return rank.has( key ) ? rank.get( key ) : Infinity;
			},
			record: record,
			firstWay: firstWay,
			users: users,
			owner: owner,
			keys: function () {
				return Array.from( records.keys() );
			}
		};
	}

	/**
	 * The steps of the route to one goal: its step and every step that it needs.
	 */
	function goalSteps( model, goal ) {
		const start = model.owner( goal );
		if ( start === null ) {
			fail( goal + ' is not on this route' );
		}
		const kept = new Set();
		const pending = [ start ];
		while ( pending.length ) {
			const key = pending.pop();
			if ( !kept.has( key ) ) {
				kept.add( key );
				model.steps.get( key ).deps.forEach( function ( other ) {
					pending.push( other );
				} );
			}
		}
		return kept;
	}

	/**
	 * Drop each edge whose end the start reaches another way, which keeps what
	 * depends on what with the fewest lines.
	 */
	function transitiveReduction( count, edges ) {
		const next = [];
		for ( let index = 0; index < count; index++ ) {
			next.push( [] );
		}
		edges.forEach( function ( edge ) {
			next[ edge.from ].push( edge.to );
		} );
		function reachesWithout( from, to ) {
			const seen = new Set();
			const stack = next[ from ].filter( function ( other ) {
				return other !== to;
			} );
			while ( stack.length ) {
				const current = stack.pop();
				if ( current === to ) {
					return true;
				}
				if ( !seen.has( current ) ) {
					seen.add( current );
					next[ current ].forEach( function ( other ) {
						stack.push( other );
					} );
				}
			}
			return false;
		}
		return edges.filter( function ( edge ) {
			return !reachesWithout( edge.from, edge.to );
		} );
	}

	/**
	 * The chapters that hold a visible step, and a line from a chapter to each
	 * later chapter with a step that needs one of its steps, after reduction.
	 */
	function chapterGraph( model, visible ) {
		const chapters = [];
		const place = new Map();
		model.chapters.forEach( function ( chapter ) {
			const steps = [];
			chapter.parts.forEach( function ( part ) {
				part.steps.forEach( function ( key ) {
					if ( visible.has( key ) ) {
						steps.push( key );
					}
				} );
			} );
			if ( steps.length ) {
				steps.forEach( function ( key ) {
					place.set( key, chapters.length );
				} );
				chapters.push( { chapter: chapter.index, title: chapter.title, steps: steps } );
			}
		} );
		const seen = new Set();
		const edges = [];
		chapters.forEach( function ( chapter, to ) {
			chapter.steps.forEach( function ( key ) {
				model.steps.get( key ).deps.forEach( function ( other ) {
					const from = place.get( other );
					if ( from !== undefined && from !== to && !seen.has( from + '>' + to ) ) {
						seen.add( from + '>' + to );
						edges.push( { from: from, to: to } );
					}
				} );
			} );
		} );
		return { chapters: chapters, edges: transitiveReduction( chapters.length, edges ) };
	}

	/**
	 * A layered drawing from top to bottom. Each chapter sits one layer below its
	 * lowest requirement, a line that spans layers bends through a point in each
	 * layer that it crosses, and barycenter sweeps order the layers so that lines
	 * cross less. Bends take a place in their layer, so no line passes behind a card.
	 */
	function layoutChapters( graph, size ) {
		const count = graph.chapters.length;
		const before = [];
		for ( let index = 0; index < count; index++ ) {
			before.push( [] );
		}
		graph.edges.forEach( function ( edge ) {
			before[ edge.to ].push( edge.from );
		} );
		const layer = [];
		const visiting = new Set();
		function layerOf( index ) {
			if ( layer[ index ] !== undefined ) {
				return layer[ index ];
			}
			if ( visiting.has( index ) ) {
				fail( 'the chapters depend on each other in a cycle' );
			}
			visiting.add( index );
			layer[ index ] = before[ index ].reduce( function ( deepest, other ) {
				return Math.max( deepest, layerOf( other ) + 1 );
			}, 0 );
			visiting.delete( index );
			return layer[ index ];
		}
		for ( let index = 0; index < count; index++ ) {
			layerOf( index );
		}
		const depth = count ? Math.max.apply( null, layer ) + 1 : 0;
		const rows = [];
		for ( let row = 0; row < depth; row++ ) {
			rows.push( [] );
		}
		const items = [];
		for ( let index = 0; index < count; index++ ) {
			const item = { kind: 'chapter', chapter: index, row: layer[ index ], up: [], down: [] };
			items.push( item );
			rows[ item.row ].push( item );
		}
		const chains = graph.edges.map( function ( edge ) {
			const chain = [ items[ edge.from ] ];
			for ( let row = layer[ edge.from ] + 1; row < layer[ edge.to ]; row++ ) {
				const bend = { kind: 'bend', row: row, up: [], down: [] };
				rows[ row ].push( bend );
				chain.push( bend );
			}
			chain.push( items[ edge.to ] );
			for ( let index = 1; index < chain.length; index++ ) {
				chain[ index ].up.push( chain[ index - 1 ] );
				chain[ index - 1 ].down.push( chain[ index ] );
			}
			return { from: edge.from, to: edge.to, chain: chain };
		} );
		function index( row ) {
			row.forEach( function ( item, position ) {
				item.position = ( position + 0.5 ) / row.length;
			} );
		}
		rows.forEach( index );
		function sweep( order, side ) {
			order.forEach( function ( row ) {
				const scored = row.map( function ( item, position ) {
					const around = item[ side ];
					const score = around.length ? around.reduce( function ( sum, other ) {
						return sum + other.position;
					}, 0 ) / around.length : item.position;
					return { item: item, score: score, position: position };
				} );
				scored.sort( function ( a, b ) {
					return a.score - b.score || a.position - b.position;
				} );
				scored.forEach( function ( entry, position ) {
					row[ position ] = entry.item;
				} );
				index( row );
			} );
		}
		for ( let round = 0; round < 8; round++ ) {
			sweep( rows.slice( 1 ), 'up' );
			sweep( rows.slice( 0, -1 ).reverse(), 'down' );
		}
		const widths = rows.map( function ( row ) {
			return row.reduce( function ( sum, item ) {
				return sum + ( item.kind === 'chapter' ? size.width : size.bend );
			}, 0 ) + Math.max( 0, row.length - 1 ) * size.gapX;
		} );
		const width = Math.max.apply( null, [ 0 ].concat( widths ) );
		rows.forEach( function ( row, number ) {
			let x = ( width - widths[ number ] ) / 2;
			const y = number * ( size.height + size.gapY );
			row.forEach( function ( item ) {
				const itemWidth = item.kind === 'chapter' ? size.width : size.bend;
				item.x = x;
				item.y = y;
				item.width = itemWidth;
				x += itemWidth + size.gapX;
			} );
		} );
		return {
			width: width,
			height: depth ? depth * size.height + ( depth - 1 ) * size.gapY : 0,
			cards: items.map( function ( item ) {
				return { chapter: item.chapter, x: item.x, y: item.y, width: item.width, height: size.height };
			} ),
			lines: chains.map( function ( entry ) {
				const points = entry.chain.map( function ( item, position ) {
					const x = item.x + item.width / 2;
					if ( position === 0 ) {
						return { x: x, y: item.y + size.height };
					}
					if ( position === entry.chain.length - 1 ) {
						return { x: x, y: item.y };
					}
					return { x: x, y: item.y + size.height / 2 };
				} );
				return { from: entry.from, to: entry.to, points: points };
			} )
		};
	}

	/**
	 * A smooth path through the points of a line: each segment leaves and meets
	 * its points vertically.
	 */
	function linePath( points ) {
		let path = 'M' + points[ 0 ].x + ' ' + points[ 0 ].y;
		for ( let index = 1; index < points.length; index++ ) {
			const from = points[ index - 1 ];
			const to = points[ index ];
			const middle = ( from.y + to.y ) / 2;
			path += ' C' + from.x + ' ' + middle + ' ' + to.x + ' ' + middle + ' ' + to.x + ' ' + to.y;
		}
		return path;
	}

	/**
	 * A smooth path from one point to another that leaves and meets its ends
	 * horizontally.
	 */
	function sidewaysPath( from, to ) {
		const middle = ( from.x + to.x ) / 2;
		return 'M' + from.x + ' ' + from.y + ' C' + middle + ' ' + from.y + ' ' + middle + ' ' + to.y +
			' ' + to.x + ' ' + to.y;
	}

	function actionOf( model, need ) {
		const kind = model.has( need.need ) ? model.record( need.need ).kind : null;
		return model.actions[ need.relation + '|' + kind ] || model.actions[ need.relation ] || need.relation;
	}

	/**
	 * What a node's first way needs and what on the route needs it, each with the
	 * action of the relation between them. A quest to keep undone is no
	 * requirement. A quest's start reads as part of its quest, as in the quest's
	 * sentence: what the start needs, the quest needs, and what needs the start
	 * leads to the quest with the action of its own need.
	 */
	function neighbourhood( model, key ) {
		const way = model.firstWay( key );
		const needs = [];
		const named = new Set( [ key ] );
		function addNeeds( list ) {
			list.forEach( function ( need ) {
				if ( !need.need || !model.has( need.need ) || model.unmet.has( need.relation ) || named.has( need.need ) ) {
					return;
				}
				named.add( need.need );
				if ( model.record( need.need ).kind === QUEST_START ) {
					const start = model.firstWay( need.need );
					addNeeds( start ? start.needs : [] );
				} else {
					needs.push( { key: need.need, action: actionOf( model, need ) } );
				}
			} );
		}
		addNeeds( way ? way.needs : [] );
		const unlocks = [];
		const users = new Set( [ key ] );
		function addUsers( node, action ) {
			model.users( node ).forEach( function ( use ) {
				if ( users.has( use.key ) ) {
					return;
				}
				users.add( use.key );
				const used = action || actionOf( model, use.need );
				if ( model.record( use.key ).kind === QUEST_START ) {
					addUsers( use.key, used );
				} else {
					unlocks.push( { key: use.key, action: used } );
				}
			} );
		}
		addUsers( key, null );
		unlocks.sort( function ( a, b ) {
			return model.rank( a.key ) - model.rank( b.key ) ||
				( model.record( a.key ).name < model.record( b.key ).name ? -1 : 1 );
		} );
		return { key: key, sentence: way ? way.sentence : null, needs: needs, unlocks: unlocks };
	}

	/**
	 * Places a neighbourhood from left to right: what the node needs, the node,
	 * and what needs it. Each column stacks its cards, so lines run only through
	 * the gaps between columns. The cards of a side that share an action form a
	 * group, kept together in the order of its first card: their lines meet at a
	 * fork in the middle of the gap, where the action's label sits, and one line
	 * joins the fork to the node. Each path runs from a need towards what needs
	 * it, and the arrows mark where needs arrive. A side without cards takes no room.
	 */
	function layoutNeighbourhood( near, size ) {
		const rows = Math.max( 1, near.needs.length, near.unlocks.length );
		const height = rows * size.height + ( rows - 1 ) * size.gapY;
		const step = size.width + size.gapX;
		const centerX = near.needs.length ? step : 0;
		const center = { key: near.key, x: centerX, y: ( height - size.height ) / 2 };
		const middle = center.y + size.height / 2;
		function grouped( entries ) {
			const actions = [];
			const members = new Map();
			entries.forEach( function ( entry ) {
				if ( !members.has( entry.action ) ) {
					members.set( entry.action, [] );
					actions.push( entry.action );
				}
				members.get( entry.action ).push( entry );
			} );
			return actions.map( function ( action ) {
				return { action: action, entries: members.get( action ) };
			} );
		}
		function side( entries, x, inward ) {
			const cards = [];
			let y = ( height - entries.length * size.height - ( entries.length - 1 ) * size.gapY ) / 2;
			const forkX = inward ? size.width + size.gapX / 2 : centerX + size.width + size.gapX / 2;
			const node = { x: inward ? centerX : centerX + size.width, y: middle };
			const groups = grouped( entries ).map( function ( group ) {
				const placed = group.entries.map( function ( entry ) {
					const card = { key: entry.key, action: entry.action, x: x, y: y };
					y += size.height + size.gapY;
					cards.push( card );
					return card;
				} );
				const fork = { x: forkX, y: ( placed[ 0 ].y + placed[ placed.length - 1 ].y + size.height ) / 2 };
				const branches = placed.map( function ( card ) {
					const end = { x: inward ? card.x + size.width : card.x, y: card.y + size.height / 2 };
					return inward ? { from: end, to: fork } : { from: fork, to: end };
				} );
				return {
					action: group.action,
					fork: fork,
					paths: [ inward ? { from: fork, to: node } : { from: node, to: fork } ].concat( branches )
				};
			} );
			const arrows = inward ? ( cards.length ? [ node ] : [] ) : groups.reduce( function ( ends, group ) {
				return ends.concat( group.paths.slice( 1 ).map( function ( path ) {
					return path.to;
				} ) );
			}, [] );
			return { cards: cards, groups: groups, arrows: arrows };
		}
		const needs = side( near.needs, 0, true );
		const unlocks = side( near.unlocks, centerX + step, false );
		return {
			width: centerX + size.width + ( unlocks.cards.length ? step : 0 ),
			height: height,
			center: center,
			needs: needs.cards,
			unlocks: unlocks.cards,
			groups: needs.groups.concat( unlocks.groups ),
			arrows: needs.arrows.concat( unlocks.arrows )
		};
	}

	/**
	 * The parts of a sentence: plain text, and the nodes that it names.
	 */
	function sentenceParts( model, sentence ) {
		const parts = [];
		let position = 0;
		sentence.replace( PLACEHOLDER, function ( match, key, offset ) {
			if ( offset > position ) {
				parts.push( { text: sentence.slice( position, offset ) } );
			}
			const source = model.record( key );
			parts.push( { key: key, name: source.name, page: source.page } );
			position = offset + match.length;
			return match;
		} );
		if ( position < sentence.length ) {
			parts.push( { text: sentence.slice( position ) } );
		}
		return parts;
	}

	function normalize( text ) {
		return String( text || '' ).toLowerCase().replace( /\s+/g, ' ' ).trim();
	}

	/**
	 * Every node of the route whose name holds the query: whole names first,
	 * then names that start with it, then words that start with it, then the
	 * rest, each in route order.
	 */
	function search( model, query, limit ) {
		const needle = normalize( query );
		if ( !needle ) {
			return [];
		}
		const found = [];
		model.keys().forEach( function ( key ) {
			const source = model.record( key );
			if ( source.kind === QUEST_START ) {
				return;
			}
			const name = normalize( source.name );
			let rank;
			if ( name === needle ) {
				rank = 0;
			} else if ( name.indexOf( needle ) === 0 ) {
				rank = 1;
			} else if ( name.indexOf( ' ' + needle ) !== -1 ) {
				rank = 2;
			} else if ( name.indexOf( needle ) !== -1 ) {
				rank = 3;
			} else {
				return;
			}
			const owner = model.owner( key );
			if ( owner !== null ) {
				found.push( { key: key, name: source.name, kind: source.kind, owner: owner, rank: rank } );
			}
		} );
		found.sort( function ( a, b ) {
			return a.rank - b.rank || model.rank( a.owner ) - model.rank( b.owner ) ||
				( a.name < b.name ? -1 : a.name > b.name ? 1 : 0 ) || ( a.key < b.key ? -1 : 1 );
		} );
		return found.slice( 0, limit );
	}

	return {
		parsePayload: parsePayload,
		createModel: createModel,
		goalSteps: goalSteps,
		transitiveReduction: transitiveReduction,
		chapterGraph: chapterGraph,
		layoutChapters: layoutChapters,
		linePath: linePath,
		sidewaysPath: sidewaysPath,
		neighbourhood: neighbourhood,
		layoutNeighbourhood: layoutNeighbourhood,
		sentenceParts: sentenceParts,
		search: search
	};
} ) );
