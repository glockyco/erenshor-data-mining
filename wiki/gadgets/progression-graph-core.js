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
	const KIND_LABELS = {
		account_state: 'Account state',
		barrier: 'Barrier',
		character: 'Character',
		class: 'Class',
		faction_standing: 'Standing',
		item: 'Item',
		mechanism: 'Mechanism',
		quest: 'Quest',
		quest_start: 'Quest start',
		spell: 'Spell',
		world_state: 'World state',
		zone: 'Area'
	};
	const FILTER_KINDS = {
		quests: [ 'quest', 'quest_start' ],
		areas: [ 'zone' ]
	};
	const FILTERS = [ 'all', 'quests', 'areas' ];

	function fail( message ) {
		throw new Error( 'Progression graph: ' + message );
	}

	function isObject( value ) {
		return value !== null && typeof value === 'object' && !Array.isArray( value );
	}

	function isCount( value ) {
		return typeof value === 'number' && isFinite( value ) && Math.floor( value ) === value && value >= 0;
	}

	function isText( value ) {
		return typeof value === 'string' && value !== '';
	}

	function normalizeRecord( key, source ) {
		if ( !isObject( source ) ) {
			fail( 'node ' + key + ' is not a record' );
		}
		if ( !isText( source.kind ) ) {
			fail( 'node ' + key + ' has no kind' );
		}
		if ( !isText( source.name ) ) {
			fail( 'node ' + key + ' has no name' );
		}
		if ( typeof source.milestone !== 'boolean' ) {
			fail( 'node ' + key + ' has no milestone flag' );
		}
		if ( source.tier !== undefined && !isCount( source.tier ) ) {
			fail( 'node ' + key + ' has an invalid tier' );
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
		const ways = source.ways;
		if ( !Array.isArray( ways ) || !ways.every( function ( way ) {
			return typeof way === 'string';
		} ) ) {
			fail( 'node ' + key + ' has invalid ways' );
		}
		let first = null;
		if ( source.first !== undefined ) {
			if ( !isCount( source.first ) || source.first < 1 || source.first > ways.length ) {
				fail( 'node ' + key + ' names a first way that it does not have' );
			}
			first = source.first - 1;
		}
		return {
			key: key,
			kind: source.kind,
			name: source.name,
			milestone: source.milestone,
			tier: source.tier === undefined ? null : source.tier,
			page: page,
			first: first,
			packed: ways.slice()
		};
	}

	/**
	 * Read the JSON payload that Module:Erenshor/Progression renders for the gadget.
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
		const targets = payload.targets;
		if ( !Array.isArray( targets ) || !targets.length || !targets.every( isText ) ) {
			fail( 'the data names no targets' );
		}
		if ( !isCount( payload.maxDepth ) || payload.maxDepth < 1 ) {
			fail( 'the data has no depth limit' );
		}
		if ( !isCount( payload.sourceLimit ) || payload.sourceLimit < 1 ) {
			fail( 'the data has no source limit' );
		}
		if ( !isObject( payload.nodes ) ) {
			fail( 'the data has no nodes' );
		}
		const records = new Map();
		Object.keys( payload.nodes ).forEach( function ( key ) {
			records.set( key, normalizeRecord( key, payload.nodes[ key ] ) );
		} );
		targets.forEach( function ( key ) {
			if ( !records.has( key ) ) {
				fail( 'the target ' + key + ' has no node' );
			}
		} );
		return {
			targets: targets.slice(),
			maxDepth: payload.maxDepth,
			sourceLimit: payload.sourceLimit,
			records: records
		};
	}

	function decodeNeed( owner, position, values ) {
		const where = 'node ' + owner + ' way ' + ( position + 1 );
		if ( !Array.isArray( values ) || !values.length || values.length > NEED_FIELDS.length ) {
			fail( where + ' has a malformed need' );
		}
		const need = {};
		NEED_FIELDS.forEach( function ( field, index ) {
			need[ field ] = values[ index ] === undefined ? null : values[ index ];
		} );
		if ( !isText( need.relation ) ) {
			fail( where + ' has a need without a relation' );
		}
		if ( need.need !== null && !isText( need.need ) ) {
			fail( where + ' has a need with an invalid step' );
		}
		[ 'slot', 'keywords', 'text' ].forEach( function ( field ) {
			if ( need[ field ] !== null && typeof need[ field ] !== 'string' ) {
				fail( where + ' has an invalid ' + field );
			}
		} );
		[ 'quantity', 'requiredLevel' ].forEach( function ( field ) {
			if ( need[ field ] !== null && ( typeof need[ field ] !== 'number' || !isFinite( need[ field ] ) ) ) {
				fail( where + ' has an invalid ' + field );
			}
		} );
		if ( need.need === null && need.text === null ) {
			fail( where + ' has a need without a step or a condition' );
		}
		need.advisory = need.advisory === true;
		need.unconfirmed = need.unconfirmed === true;
		return need;
	}

	/**
	 * Wrap a parsed payload. Ways are decoded when a caller first reads them.
	 */
	function createModel( payload ) {
		const records = payload.records;
		const decoded = new Map();

		function record( key ) {
			const found = records.get( key );
			if ( !found ) {
				fail( 'the data lacks the step ' + key );
			}
			return found;
		}

		function ways( key ) {
			let list = decoded.get( key );
			if ( !list ) {
				const source = record( key );
				list = source.packed.map( function ( packed, index ) {
					let values;
					try {
						values = JSON.parse( packed );
					} catch ( error ) {
						fail( 'node ' + key + ' way ' + ( index + 1 ) + ' cannot be read' );
					}
					if ( !Array.isArray( values ) ) {
						fail( 'node ' + key + ' way ' + ( index + 1 ) + ' is not a list of needs' );
					}
					return {
						index: index,
						first: index === source.first,
						needs: values.map( function ( values ) {
							return decodeNeed( key, index, values );
						} )
					};
				} );
				decoded.set( key, list );
			}
			return list;
		}

		function firstWay( key ) {
			const source = record( key );
			return source.first === null ? null : ways( key )[ source.first ];
		}

		return {
			targets: payload.targets,
			maxDepth: payload.maxDepth,
			sourceLimit: payload.sourceLimit,
			has: function ( key ) {
				return records.has( key );
			},
			record: record,
			ways: ways,
			firstWay: firstWay,
			keys: function () {
				return Array.from( records.keys() );
			}
		};
	}

	function kindLabel( kind ) {
		if ( Object.prototype.hasOwnProperty.call( KIND_LABELS, kind ) ) {
			return KIND_LABELS[ kind ];
		}
		const words = kind.replace( /_/g, ' ' );
		return words.charAt( 0 ).toUpperCase() + words.slice( 1 );
	}

	function stepName( record ) {
		return record.kind === 'quest_start' ? 'Start ' + record.name : record.name;
	}

	function tierLabel( tier ) {
		return tier === null ? 'No playthrough tier recorded' : 'Playthrough tier ' + tier;
	}

	function hiddenStepsLabel( count ) {
		return count === 1 ? '1 hidden step' : count + ' hidden steps';
	}

	// Steps in playthrough order: by tier, untiered steps last, then by key.
	function stepOrder( model ) {
		return function ( left, right ) {
			const a = model.record( left ).tier;
			const b = model.record( right ).tier;
			const x = a === null ? Infinity : a;
			const y = b === null ? Infinity : b;
			if ( x !== y ) {
				return x < y ? -1 : 1;
			}
			return left < right ? -1 : left > right ? 1 : 0;
		};
	}

	function buildView( keys, edges ) {
		const order = new Map();
		const deps = new Map();
		const dependents = new Map();
		keys.forEach( function ( key, index ) {
			order.set( key, index );
			deps.set( key, [] );
			dependents.set( key, [] );
		} );
		edges.forEach( function ( edge ) {
			deps.get( edge.to ).push( edge.from );
			dependents.get( edge.from ).push( edge.to );
		} );
		function byOrder( left, right ) {
			return order.get( left ) - order.get( right );
		}
		deps.forEach( function ( list ) {
			list.sort( byOrder );
		} );
		dependents.forEach( function ( list ) {
			list.sort( byOrder );
		} );
		return { keys: keys, order: order, deps: deps, dependents: dependents, edges: edges };
	}

	/**
	 * The overview of D3: the milestones on the first-way route of the roots, and
	 * the roots themselves. A step depends on the nearest steps that its first way
	 * reaches through steps that are not milestones.
	 */
	function overview( model, roots ) {
		const closure = new Set();
		const steps = new Set();
		const pending = roots.slice();
		while ( pending.length ) {
			const key = pending.pop();
			if ( closure.has( key ) ) {
				continue;
			}
			closure.add( key );
			if ( model.record( key ).milestone ) {
				steps.add( key );
			}
			const way = model.firstWay( key );
			if ( way ) {
				way.needs.forEach( function ( need ) {
					if ( need.need ) {
						pending.push( need.need );
					}
				} );
			}
		}
		roots.forEach( function ( key ) {
			steps.add( key );
		} );
		const keys = Array.from( steps ).sort( stepOrder( model ) );
		const frontiers = new Map();

		function nearest( key, path ) {
			if ( frontiers.has( key ) ) {
				return frontiers.get( key );
			}
			if ( path.has( key ) ) {
				fail( 'the first ways cycle at ' + key );
			}
			path.add( key );
			const found = new Set();
			const way = model.firstWay( key );
			if ( way ) {
				way.needs.forEach( function ( need ) {
					if ( !need.need ) {
						return;
					}
					if ( steps.has( need.need ) ) {
						found.add( need.need );
					} else {
						nearest( need.need, path ).forEach( function ( step ) {
							found.add( step );
						} );
					}
				} );
			}
			path.delete( key );
			frontiers.set( key, found );
			return found;
		}

		const edges = [];
		keys.forEach( function ( key ) {
			const found = new Set();
			const way = model.firstWay( key );
			if ( way ) {
				way.needs.forEach( function ( need ) {
					if ( !need.need ) {
						return;
					}
					if ( steps.has( need.need ) ) {
						found.add( need.need );
					} else {
						nearest( need.need, new Set( [ key ] ) ).forEach( function ( step ) {
							found.add( step );
						} );
					}
				} );
			}
			found.delete( key );
			found.forEach( function ( from ) {
				edges.push( { from: from, to: key, direct: true, hidden: [] } );
			} );
		} );
		return buildView( keys, edges );
	}

	/**
	 * Keep a step with what it needs (its ancestors) or what it unlocks (its
	 * descendants, the reversed edges).
	 */
	function restrict( view, focus, direction ) {
		if ( !view.deps.has( focus ) ) {
			fail( focus + ' is not on this route' );
		}
		if ( direction !== 'needs' && direction !== 'unlocks' ) {
			fail( 'unknown direction ' + direction );
		}
		const next = direction === 'needs' ? view.deps : view.dependents;
		const keep = new Set( [ focus ] );
		const pending = [ focus ];
		while ( pending.length ) {
			next.get( pending.pop() ).forEach( function ( other ) {
				if ( !keep.has( other ) ) {
					keep.add( other );
					pending.push( other );
				}
			} );
		}
		return buildView(
			view.keys.filter( function ( key ) {
				return keep.has( key );
			} ),
			view.edges.filter( function ( edge ) {
				return keep.has( edge.from ) && keep.has( edge.to );
			} )
		);
	}

	/**
	 * Keep only quests or areas, and the steps in `always`. An edge between two
	 * kept steps names the hidden steps that lie between them on the route.
	 */
	function filterView( view, model, filter, always ) {
		if ( filter === 'all' ) {
			return view;
		}
		const kinds = FILTER_KINDS[ filter ];
		if ( !kinds ) {
			fail( 'unknown filter ' + filter );
		}
		const kept = new Set( view.keys.filter( function ( key ) {
			return kinds.indexOf( model.record( key ).kind ) !== -1 || always.has( key );
		} ) );
		function byOrder( left, right ) {
			return view.order.get( left ) - view.order.get( right );
		}
		const edges = [];
		view.keys.forEach( function ( to ) {
			if ( !kept.has( to ) ) {
				return;
			}
			// The hidden steps that reach this step through hidden steps only,
			// and the kept steps right before them.
			const between = new Set();
			const sources = new Set();
			const pending = [ to ];
			while ( pending.length ) {
				view.deps.get( pending.pop() ).forEach( function ( from ) {
					if ( kept.has( from ) ) {
						sources.add( from );
					} else if ( !between.has( from ) ) {
						between.add( from );
						pending.push( from );
					}
				} );
			}
			Array.from( sources ).sort( byOrder ).forEach( function ( from ) {
				const hidden = new Set();
				const queue = [ from ];
				while ( queue.length ) {
					view.dependents.get( queue.pop() ).forEach( function ( next ) {
						if ( between.has( next ) && !hidden.has( next ) ) {
							hidden.add( next );
							queue.push( next );
						}
					} );
				}
				edges.push( {
					from: from,
					to: to,
					direct: view.deps.get( to ).indexOf( from ) !== -1,
					hidden: Array.from( hidden ).sort( byOrder )
				} );
			} );
		} );
		return buildView(
			view.keys.filter( function ( key ) {
				return kept.has( key );
			} ),
			edges
		);
	}

	/**
	 * One column per tier, untiered steps last. Repeated barycenter sweeps order
	 * each column by the positions of its steps' neighbours.
	 */
	function orderColumns( view, model, sweeps ) {
		const byTier = new Map();
		view.keys.forEach( function ( key ) {
			const tier = model.record( key ).tier;
			if ( !byTier.has( tier ) ) {
				byTier.set( tier, [] );
			}
			byTier.get( tier ).push( key );
		} );
		const tiers = Array.from( byTier.keys() ).sort( function ( a, b ) {
			if ( a === b ) {
				return 0;
			}
			if ( a === null ) {
				return 1;
			}
			if ( b === null ) {
				return -1;
			}
			return a - b;
		} );
		const columns = tiers.map( function ( tier ) {
			return { tier: tier, keys: byTier.get( tier ) };
		} );
		const position = new Map();
		function index( column ) {
			column.keys.forEach( function ( key, row ) {
				position.set( key, ( row + 0.5 ) / column.keys.length );
			} );
		}
		columns.forEach( index );
		function sweep( list, neighbours ) {
			list.forEach( function ( column ) {
				const scored = column.keys.map( function ( key, row ) {
					const around = neighbours.get( key );
					let score = position.get( key );
					if ( around.length ) {
						score = around.reduce( function ( sum, other ) {
							return sum + position.get( other );
						}, 0 ) / around.length;
					}
					return { key: key, score: score, row: row };
				} );
				scored.sort( function ( a, b ) {
					return a.score - b.score || a.row - b.row;
				} );
				column.keys = scored.map( function ( entry ) {
					return entry.key;
				} );
				index( column );
			} );
		}
		for ( let round = 0; round < sweeps; round++ ) {
			sweep( columns.slice( 1 ), view.deps );
			sweep( columns.slice( 0, -1 ).reverse(), view.dependents );
		}
		return columns;
	}

	function placeColumns( columns, heightOf, spacing ) {
		const positions = new Map();
		let width = 0;
		let height = 0;
		columns.forEach( function ( column, index ) {
			const x = spacing.left + index * ( spacing.nodeWidth + spacing.columnGap );
			let y = spacing.top;
			column.keys.forEach( function ( key ) {
				const size = heightOf( key );
				positions.set( key, { x: x, y: y, width: spacing.nodeWidth, height: size, column: index } );
				y += size + spacing.rowGap;
			} );
			width = Math.max( width, x + spacing.nodeWidth + spacing.left );
			height = Math.max( height, y );
		} );
		return { positions: positions, width: width, height: height };
	}

	function curve( start, end ) {
		const bend = Math.max( 24, ( end.x - start.x ) / 2 );
		return 'M' + start.x + ' ' + start.y + ' C' + ( start.x + bend ) + ' ' + start.y + ' ' +
			( end.x - bend ) + ' ' + end.y + ' ' + end.x + ' ' + end.y;
	}

	/**
	 * Lines from each requirement to the step that needs it. A step with several
	 * requirements gathers them at a junction before it, because its drawn way
	 * needs all of them. The label of a line that hides steps sits in the gap
	 * after its source, and the labels of one source stack, so that neither
	 * meets the junction labels of the next column nor each other.
	 */
	function edgeRoutes( view, positions, options ) {
		const incoming = new Map();
		view.edges.forEach( function ( edge ) {
			if ( !incoming.has( edge.to ) ) {
				incoming.set( edge.to, [] );
			}
			incoming.get( edge.to ).push( edge );
		} );
		const labelled = new Map();
		const routes = [];
		const junctions = [];
		view.keys.forEach( function ( to ) {
			const edges = incoming.get( to );
			if ( !edges ) {
				return;
			}
			const target = positions.get( to );
			const end = { x: target.x, y: target.y + options.anchor };
			let join = end;
			if ( edges.length > 1 ) {
				join = { x: target.x - options.junctionGap, y: end.y };
				junctions.push( { key: to, x: join.x, y: join.y, count: edges.length } );
				routes.push( { from: null, to: to, d: 'M' + join.x + ' ' + join.y + ' L' + end.x + ' ' + end.y, direct: true, hidden: [], label: null } );
			}
			edges.forEach( function ( edge ) {
				const source = positions.get( edge.from );
				const start = { x: source.x + source.width, y: source.y + options.anchor };
				let label = null;
				if ( edge.hidden.length ) {
					const before = labelled.get( edge.from ) || 0;
					labelled.set( edge.from, before + 1 );
					label = { x: start.x + options.labelOffset, y: start.y - options.labelSpacing * ( before + 0.5 ) };
				}
				routes.push( {
					from: edge.from,
					to: to,
					d: curve( start, join ),
					direct: edge.direct,
					hidden: edge.hidden,
					label: label
				} );
			} );
		} );
		return { routes: routes, junctions: junctions };
	}

	function normalize( text ) {
		return String( text || '' ).toLowerCase().replace( /\s+/g, ' ' ).trim();
	}

	/**
	 * Every step of the data whose name holds the query: whole names first, then
	 * names that start with it, then words that start with it, then the rest.
	 */
	function search( model, query, limit ) {
		const needle = normalize( query );
		if ( !needle ) {
			return [];
		}
		const found = [];
		model.keys().forEach( function ( key ) {
			const record = model.record( key );
			const name = normalize( stepName( record ) );
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
			found.push( { key: key, rank: rank, record: record } );
		} );
		found.sort( function ( a, b ) {
			const x = a.record.tier === null ? Infinity : a.record.tier;
			const y = b.record.tier === null ? Infinity : b.record.tier;
			if ( a.rank !== b.rank ) {
				return a.rank - b.rank;
			}
			if ( x !== y ) {
				return x < y ? -1 : 1;
			}
			const left = stepName( a.record );
			const right = stepName( b.record );
			if ( left !== right ) {
				return left < right ? -1 : 1;
			}
			return a.key < b.key ? -1 : a.key > b.key ? 1 : 0;
		} );
		return found.slice( 0, limit ).map( function ( entry ) {
			return { key: entry.key, name: stepName( entry.record ), kind: entry.record.kind, tier: entry.record.tier };
		} );
	}

	/**
	 * The steps that the arrow keys reach from a step: what it needs and what it
	 * unlocks, nearest first, and the steps above and below it in its column.
	 */
	function neighbours( view, columns, key ) {
		const places = new Map();
		columns.forEach( function ( column, index ) {
			column.keys.forEach( function ( other, row ) {
				places.set( other, { column: index, row: row } );
			} );
		} );
		const here = places.get( key );
		if ( !here ) {
			fail( key + ' is not drawn' );
		}
		function nearest( list ) {
			return list.slice().sort( function ( a, b ) {
				const x = places.get( a );
				const y = places.get( b );
				return Math.abs( x.column - here.column ) - Math.abs( y.column - here.column ) ||
					Math.abs( x.row - here.row ) - Math.abs( y.row - here.row ) ||
					x.row - y.row;
			} );
		}
		const column = columns[ here.column ].keys;
		return {
			needs: nearest( view.deps.get( key ) ),
			unlocks: nearest( view.dependents.get( key ) ),
			up: here.row > 0 ? column[ here.row - 1 ] : null,
			down: here.row < column.length - 1 ? column[ here.row + 1 ] : null
		};
	}

	const reverseFirstWays = new WeakMap();

	/**
	 * The nearest drawn step whose first way leads to a step, for a step that
	 * the details never mention because it lies beyond their depth limit.
	 */
	function routeOwner( model, view, key ) {
		if ( view.deps.has( key ) ) {
			return key;
		}
		let reverse = reverseFirstWays.get( model );
		if ( !reverse ) {
			reverse = new Map();
			model.keys().forEach( function ( other ) {
				const way = model.firstWay( other );
				if ( way ) {
					way.needs.forEach( function ( need ) {
						if ( need.need ) {
							if ( !reverse.has( need.need ) ) {
								reverse.set( need.need, [] );
							}
							reverse.get( need.need ).push( other );
						}
					} );
				}
			} );
			reverseFirstWays.set( model, reverse );
		}
		const seen = new Set( [ key ] );
		let layer = [ key ];
		while ( layer.length ) {
			const next = [];
			const drawn = [];
			layer.forEach( function ( step ) {
				( reverse.get( step ) || [] ).forEach( function ( other ) {
					if ( seen.has( other ) ) {
						return;
					}
					seen.add( other );
					if ( view.deps.has( other ) ) {
						drawn.push( other );
					} else {
						next.push( other );
					}
				} );
			} );
			if ( drawn.length ) {
				return drawn.sort( function ( left, right ) {
					return view.order.get( left ) - view.order.get( right );
				} )[ 0 ];
			}
			layer = next;
		}
		return null;
	}

	/**
	 * The ways and sources of every overview step, in the order and depth of the
	 * text that Module:Erenshor/Progression renders, so that every label it needs
	 * is in the data. A step that is drawn, or that the text already expanded, is
	 * a reference. `owners` maps each step to the overview step whose detail
	 * first mentions it.
	 */
	function detailForest( model, base ) {
		const drawn = new Set( base.keys );
		const seen = new Set();
		const owners = new Map();
		const trees = new Map();
		let owner = null;

		function waysOf( key, depth ) {
			const record = model.record( key );
			const list = model.ways( key );
			const tree = { empty: !list.length, visible: [], sources: [], entrances: [] };
			const visible = [];
			const sources = [];
			const entrances = [];
			list.forEach( function ( way ) {
				if ( record.kind === 'zone' && way.needs.length === 1 && way.needs[ 0 ].relation === 'zone line' ) {
					entrances.push( way );
				} else if ( !record.milestone && way.index >= model.sourceLimit ) {
					sources.push( way );
				} else {
					visible.push( way );
				}
			} );
			// The text expands visible ways first, then the source groups.
			tree.visible = visible.map( function ( way ) {
				return wayOf( way, depth );
			} );
			tree.sources = sources.map( function ( way ) {
				return wayOf( way, depth );
			} );
			tree.entrances = entrances.map( function ( way ) {
				return wayOf( way, depth );
			} );
			return tree;
		}

		function wayOf( way, depth ) {
			return {
				first: way.first,
				needs: way.needs.map( function ( need ) {
					return needOf( need, depth );
				} )
			};
		}

		function needOf( need, depth ) {
			const key = need.need;
			if ( !key ) {
				return { need: need, key: null, state: 'plain' };
			}
			model.record( key );
			if ( !owners.has( key ) ) {
				owners.set( key, owner );
			}
			if ( drawn.has( key ) || seen.has( key ) ) {
				return { need: need, key: key, state: 'reference' };
			}
			if ( depth >= model.maxDepth ) {
				return { need: need, key: key, state: 'limit' };
			}
			seen.add( key );
			return { need: need, key: key, state: 'expanded', ways: waysOf( key, depth + 1 ) };
		}

		base.keys.forEach( function ( key ) {
			owner = key;
			owners.set( key, key );
			seen.add( key );
			trees.set( key, waysOf( key, 1 ) );
		} );
		return { trees: trees, owners: owners };
	}

	/**
	 * The words of a need, as the text renders them: what comes before the step's
	 * name, the step, and what follows it.
	 */
	function needWording( model, need ) {
		let lead;
		if ( need.relation === 'defeated' || need.relation === 'defeat' ) {
			lead = need.quantity !== null && need.quantity > 1 ? 'Defeat all ' + need.quantity + ' ' : 'Defeat ';
		} else {
			lead = need.relation + ': ';
			if ( need.quantity !== null ) {
				lead += need.quantity + ' x ';
			}
		}
		let trail = '';
		if ( need.text !== null ) {
			trail += need.need ? ' (' + need.text + ')' : need.text;
		}
		if ( need.slot !== null ) {
			trail += ' (slot ' + need.slot + ')';
		}
		if ( need.keywords !== null ) {
			trail += ' (keywords: "' + need.keywords + '")';
		}
		if ( need.requiredLevel !== null ) {
			trail += ' (level ' + need.requiredLevel + ')';
		}
		if ( need.advisory ) {
			trail += ' (advisory)';
		}
		if ( need.unconfirmed ) {
			trail += ' (player access unconfirmed)';
		}
		return {
			lead: lead,
			key: need.need,
			name: need.need ? stepName( model.record( need.need ) ) : null,
			trail: trail
		};
	}

	return {
		FILTERS: FILTERS,
		parsePayload: parsePayload,
		createModel: createModel,
		kindLabel: kindLabel,
		stepName: stepName,
		tierLabel: tierLabel,
		hiddenStepsLabel: hiddenStepsLabel,
		overview: overview,
		restrict: restrict,
		filterView: filterView,
		orderColumns: orderColumns,
		placeColumns: placeColumns,
		edgeRoutes: edgeRoutes,
		search: search,
		neighbours: neighbours,
		detailForest: detailForest,
		routeOwner: routeOwner,
		needWording: needWording
	};
} ) );
