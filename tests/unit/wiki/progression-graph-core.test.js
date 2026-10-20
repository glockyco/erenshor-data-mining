const fs = require( 'node:fs' );
const path = require( 'node:path' );
const test = require( 'node:test' );
const vm = require( 'node:vm' );
const assert = require( 'node:assert/strict' );
const core = require( '../../../wiki/gadgets/progression-graph-core.js' );

// A record in the form that Module:Erenshor/Progression puts into the payload:
// packed ways, a one-based first way, and an omitted page for page = name.
const node = ( kind, name, tier, milestone, ways, extra ) => Object.assign(
	{ kind, name, milestone, ways: ways.map( ( needs ) => JSON.stringify( needs ) ), first: 1 },
	tier === null ? {} : { tier },
	extra || {}
);
const meatWays = [ 1, 2, 3, 4, 5, 6 ].map( () => [ [ 'drop', 'character:wolf' ] ] );

const routeNodes = () => ( {
	'zone:stowaway': node( 'zone', "Stowaway's Step", 0, true, [ [] ] ),
	'quest_start:errand': node( 'quest_start', 'An Errand', 0, false, [ [ [ 'talk to', 'character:guard' ] ] ] ),
	'character:guard': node( 'character', 'A Guard', 0, false, [ [ [ 'in zone', 'zone:stowaway' ] ] ] ),
	'quest:errand': node( 'quest', 'An Errand', 1, true, [ [ [ 'quest start', 'quest_start:errand' ] ] ] ),
	'item:key': node( 'item', 'Iron Key', 2, true, [ [ [ 'quest reward', 'quest:errand' ] ] ] ),
	'barrier:door': node( 'barrier', 'Iron Door', 3, true, [ [ [ 'key', 'item:key' ] ] ], { page: false } ),
	'zone:vault': node( 'zone', 'The Vault', 4, true, [
		[ [ 'zone line', 'zone:stowaway' ] ],
		[ [ 'zone line', 'zone:stowaway' ] ],
		[ [ 'barrier', 'barrier:door' ], [ 'zone line', 'zone:stowaway' ] ]
	], { first: 3 } ),
	'character:wolf': node( 'character', 'A Wolf', 0, false, [ [ [ 'in zone', 'zone:stowaway' ] ] ] ),
	'item:meat': node( 'item', 'Wolf Meat', 0, false, meatWays ),
	'character:priest': node( 'character', 'A Priest', 4, false, [ [ [ 'in zone', 'zone:vault' ] ] ] ),
	'mechanism:bridge': node( 'mechanism', 'A bridge', 2, false, [ [ [ 'after', 'item:key' ] ] ], { page: false } ),
	'quest:ritual': node( 'quest', 'The Ritual', 5, true, [
		[ [ 'turn in to', 'character:priest' ], [ 'required item', 'item:meat', 2 ], [ 'after', 'mechanism:bridge' ] ],
		[ [ 'alternative', 'zone:vault' ] ]
	] ),
	'zone:plane': node( 'zone', 'The Plane', 6, true, [
		[ [ 'quest done', 'quest:ritual' ], [ 'planning slot', 'item:key', null, 'PlanarX' ] ]
	] )
} );

const payload = ( nodes, overrides ) => JSON.stringify( Object.assign(
	{ targets: [ 'zone:plane' ], maxDepth: 6, sourceLimit: 4, unmet: [ 'quest not done' ], nodes: nodes || routeNodes() },
	overrides
) );
const model = ( text ) => core.createModel( core.parsePayload( text || payload() ) );
const edges = ( view ) => view.edges.map( ( edge ) => edge.from + ' > ' + edge.to ).sort();

test( 'publishes the browser global inside a ResourceLoader module wrapper', () => {
	const context = { module: { exports: {} } };
	context.self = context;
	const source = fs.readFileSync(
		path.join( __dirname, '../../../wiki/gadgets/progression-graph-core.js' ),
		'utf8'
	);

	vm.runInNewContext( source, context );

	assert.equal( typeof context.ErenshorProgressionGraphCore.parsePayload, 'function' );
	assert.deepEqual( context.module.exports, {} );
} );

test( 'reads pages, first ways, and tiers from the compact records', () => {
	const graph = model();

	assert.equal( graph.record( 'zone:vault' ).page, 'The Vault' );
	assert.equal( graph.record( 'barrier:door' ).page, null );
	assert.equal( graph.record( 'zone:vault' ).first, 2 );
	assert.equal( graph.firstWay( 'zone:vault' ).needs[ 0 ].need, 'barrier:door' );
	assert.deepEqual( graph.ways( 'zone:plane' )[ 0 ].needs[ 1 ], {
		relation: 'planning slot',
		need: 'item:key',
		quantity: null,
		slot: 'PlanarX',
		keywords: null,
		text: null,
		advisory: false,
		unconfirmed: false,
		requiredLevel: null
	} );
	assert.equal( core.parsePayload( payload( { 'zone:plane': node( 'zone', 'P', null, true, [], { first: undefined } ) } ) )
		.records.get( 'zone:plane' ).tier, null );
} );

test( 'rejects data that the view could not have rendered', () => {
	assert.throws( () => core.parsePayload( '{"targets":' ), /cannot be read/ );
	assert.throws( () => core.parsePayload( payload( undefined, { targets: [ 'zone:elsewhere' ] } ) ),
		/target zone:elsewhere has no node/ );
	assert.throws( () => core.parsePayload( payload( undefined, { maxDepth: 0 } ) ), /depth limit/ );
	assert.throws( () => core.parsePayload( payload( undefined, { sourceLimit: undefined } ) ), /source limit/ );
	assert.throws( () => core.parsePayload( payload( undefined, { unmet: undefined } ) ), /unmet relations/ );
	const nodes = routeNodes();
	nodes[ 'zone:plane' ].first = 2;
	assert.throws( () => core.parsePayload( payload( nodes ) ), /first way that it does not have/ );
	const unnamed = routeNodes();
	unnamed[ 'item:key' ].ways = [ JSON.stringify( [ [ 'quest reward' ] ] ) ];
	assert.throws( () => model( payload( unnamed ) ).ways( 'item:key' ), /without a step or a condition/ );
} );

test( 'the overview joins milestones through the first ways of other steps', () => {
	const view = core.overview( model(), [ 'zone:plane' ] );

	assert.deepEqual( view.keys, [
		'zone:stowaway', 'quest:errand', 'item:key', 'barrier:door', 'zone:vault', 'quest:ritual', 'zone:plane'
	] );
	// The Ritual reaches the vault through its priest, the key through the
	// bridge, and Stowaway's Step through the meat's wolf.
	assert.deepEqual( view.deps.get( 'quest:ritual' ), [ 'zone:stowaway', 'item:key', 'zone:vault' ] );
	// The quest start and its giver lead to the giver's zone.
	assert.deepEqual( view.deps.get( 'quest:errand' ), [ 'zone:stowaway' ] );
	// The vault's first way is its gated entrance, not a gate-free one.
	assert.deepEqual( view.deps.get( 'zone:vault' ), [ 'zone:stowaway', 'barrier:door' ] );
	assert.ok( !view.deps.has( 'mechanism:bridge' ) );
} );

test( 'every edge of the overview runs to a later tier column', () => {
	const graph = model();
	const view = core.overview( graph, [ 'zone:plane' ] );
	const columns = core.orderColumns( view, graph, 8 );
	const column = new Map();
	columns.forEach( ( entry, index ) => entry.keys.forEach( ( key ) => column.set( key, index ) ) );

	assert.deepEqual( columns.map( ( entry ) => entry.tier ), [ 0, 1, 2, 3, 4, 5, 6 ] );
	assert.ok( view.edges.length > 0 );
	for ( const edge of view.edges ) {
		assert.ok( column.get( edge.from ) < column.get( edge.to ), edge.from + ' > ' + edge.to );
		assert.ok( graph.record( edge.from ).tier < graph.record( edge.to ).tier );
	}
} );

test( 'a quest to keep undone is no requirement of the route', () => {
	const nodes = routeNodes();
	// The key can only be had before The Ritual is done, which needs the key itself.
	nodes[ 'item:key' ].ways = [ JSON.stringify( [ [ 'quest reward', 'quest:errand' ], [ 'quest not done', 'quest:ritual' ] ] ) ];
	const graph = model( payload( nodes ) );
	const view = core.overview( graph, [ 'barrier:door' ] );
	const forest = core.detailForest( graph, view );

	assert.deepEqual( view.keys, [ 'zone:stowaway', 'quest:errand', 'item:key', 'barrier:door' ] );
	assert.deepEqual( view.deps.get( 'item:key' ), [ 'quest:errand' ] );
	const undone = forest.trees.get( 'item:key' ).visible[ 0 ].needs[ 1 ];
	assert.equal( undone.state, 'unmet' );
	assert.equal( undone.ways, undefined );
	assert.equal( core.routeOwner( graph, view, 'character:priest' ), null );
} );

test( 'untiered steps take the last column', () => {
	const nodes = {
		'zone:plane': node( 'zone', 'P', null, true, [ [ [ 'after', 'item:a' ] ] ] ),
		'item:a': node( 'item', 'A', 3, true, [ [] ] )
	};
	const graph = model( payload( nodes ) );
	const columns = core.orderColumns( core.overview( graph, [ 'zone:plane' ] ), graph, 2 );

	assert.deepEqual( columns.map( ( entry ) => entry.tier ), [ 3, null ] );
} );

test( 'barycenter sweeps uncross the lines between two columns', () => {
	const nodes = {
		'item:a1': node( 'item', 'A1', 0, true, [ [] ] ),
		'item:a2': node( 'item', 'A2', 0, true, [ [] ] ),
		'item:b1': node( 'item', 'B1', 1, true, [ [ [ 'from', 'item:a2' ] ] ] ),
		'item:b2': node( 'item', 'B2', 1, true, [ [ [ 'from', 'item:a1' ] ] ] )
	};
	const graph = model( payload( nodes, { targets: [ 'item:b1', 'item:b2' ] } ) );
	const columns = core.orderColumns( core.overview( graph, [ 'item:b1', 'item:b2' ] ), graph, 4 );

	assert.deepEqual( columns[ 0 ].keys, [ 'item:a1', 'item:a2' ] );
	assert.deepEqual( columns[ 1 ].keys, [ 'item:b2', 'item:b1' ] );
} );

test( 'a step with several requirements gathers them at one junction', () => {
	const graph = model();
	const view = core.overview( graph, [ 'zone:plane' ] );
	const layout = core.placeColumns( core.orderColumns( view, graph, 8 ), () => 40, {
		left: 10, top: 30, nodeWidth: 200, columnGap: 80, rowGap: 10
	} );
	const routes = core.edgeRoutes( view, layout.positions, { anchor: 20, junctionGap: 24, labelOffset: 28, labelSpacing: 13 } );
	const plane = layout.positions.get( 'zone:plane' );
	const junction = routes.junctions.find( ( entry ) => entry.key === 'zone:plane' );

	assert.deepEqual( junction, { key: 'zone:plane', x: plane.x - 24, y: plane.y + 20, count: 2 } );
	assert.ok( !routes.junctions.some( ( entry ) => entry.key === 'barrier:door' ) );
	const intoPlane = routes.routes.filter( ( route ) => route.to === 'zone:plane' && route.from );
	assert.deepEqual( intoPlane.map( ( route ) => route.from ).sort(), [ 'item:key', 'quest:ritual' ] );
	assert.ok( intoPlane.every( ( route ) => route.d.endsWith( ( plane.x - 24 ) + ' ' + ( plane.y + 20 ) ) ) );
} );

test( 'labels of lines that hide steps stack in the gap after their source', () => {
	const graph = model();
	const quests = core.filterView( core.overview( graph, [ 'zone:plane' ] ), graph, 'quests', new Set( [ 'zone:plane' ] ) );
	const layout = core.placeColumns( core.orderColumns( quests, graph, 8 ), () => 40, {
		left: 10, top: 30, nodeWidth: 200, columnGap: 80, rowGap: 10
	} );
	const routes = core.edgeRoutes( quests, layout.positions, { anchor: 20, junctionGap: 24, labelOffset: 28, labelSpacing: 13 } );
	const errand = layout.positions.get( 'quest:errand' );
	const labels = routes.routes.filter( ( route ) => route.from === 'quest:errand' ).map( ( route ) => route.label );

	assert.equal( labels.length, 2 );
	assert.ok( labels.every( ( label ) => label.x === errand.x + errand.width + 28 ) );
	assert.notEqual( labels[ 0 ].y, labels[ 1 ].y );
	assert.equal( routes.routes.find( ( route ) => route.from === 'quest:ritual' ).label, null );
} );

test( 'what an item unlocks follows the reversed edges of its route', () => {
	const view = core.overview( model(), [ 'zone:plane' ] );
	const unlocks = core.restrict( view, 'item:key', 'unlocks' );
	const needs = core.restrict( view, 'zone:vault', 'needs' );

	assert.deepEqual( unlocks.keys, [ 'item:key', 'barrier:door', 'zone:vault', 'quest:ritual', 'zone:plane' ] );
	assert.deepEqual( unlocks.deps.get( 'item:key' ), [] );
	assert.deepEqual( needs.keys, [ 'zone:stowaway', 'quest:errand', 'item:key', 'barrier:door', 'zone:vault' ] );
	assert.throws( () => core.restrict( unlocks, 'quest:errand', 'needs' ), /not on this route/ );
} );

test( 'a filtered edge names the steps that it hides', () => {
	const graph = model();
	const view = core.overview( graph, [ 'zone:plane' ] );
	const quests = core.filterView( view, graph, 'quests', new Set( [ 'zone:plane' ] ) );
	const edge = ( from, to ) => quests.edges.find( ( entry ) => entry.from === from && entry.to === to );

	assert.deepEqual( quests.keys, [ 'quest:errand', 'quest:ritual', 'zone:plane' ] );
	assert.deepEqual( edges( quests ), [
		'quest:errand > quest:ritual', 'quest:errand > zone:plane', 'quest:ritual > zone:plane'
	] );
	assert.deepEqual( edge( 'quest:errand', 'quest:ritual' ), {
		from: 'quest:errand', to: 'quest:ritual', direct: false, hidden: [ 'item:key', 'barrier:door', 'zone:vault' ]
	} );
	assert.deepEqual( edge( 'quest:ritual', 'zone:plane' ).hidden, [] );
	assert.equal( edge( 'quest:ritual', 'zone:plane' ).direct, true );
	assert.equal( core.hiddenStepsLabel( 1 ), '1 hidden step' );
	assert.equal( core.hiddenStepsLabel( 3 ), '3 hidden steps' );

	const areas = core.filterView( view, graph, 'areas', new Set( [ 'zone:plane' ] ) );
	assert.deepEqual( areas.keys, [ 'zone:stowaway', 'zone:vault', 'zone:plane' ] );
	assert.deepEqual( areas.edges.find( ( entry ) => entry.from === 'zone:vault' ).hidden, [ 'quest:ritual' ] );
} );

test( 'details collapse common sources and gate-free entrances like the text', () => {
	const graph = model();
	const forest = core.detailForest( graph, core.overview( graph, [ 'zone:plane' ] ) );
	const vault = forest.trees.get( 'zone:vault' );
	const ritual = forest.trees.get( 'quest:ritual' ).visible[ 0 ];
	const meat = ritual.needs[ 1 ];

	assert.equal( vault.entrances.length, 2 );
	assert.equal( vault.visible.length, 1 );
	assert.equal( vault.visible[ 0 ].first, true );
	assert.equal( meat.state, 'expanded' );
	assert.equal( meat.ways.visible.length, 4 );
	assert.equal( meat.ways.sources.length, 2 );
	// The first source expands the wolf, and later sources refer to it.
	assert.equal( meat.ways.visible[ 0 ].needs[ 0 ].state, 'expanded' );
	assert.equal( meat.ways.visible[ 1 ].needs[ 0 ].state, 'reference' );
	// Drawn steps are references, not repeated.
	assert.equal( ritual.needs[ 0 ].ways.visible[ 0 ].needs[ 0 ].state, 'reference' );
	assert.equal( forest.owners.get( 'character:wolf' ), 'quest:ritual' );
	assert.equal( forest.owners.get( 'character:guard' ), 'quest:errand' );
	assert.equal( forest.owners.get( 'zone:vault' ), 'zone:vault' );
} );

test( 'a milestone keeps every way, and details stop at the depth limit', () => {
	const nodes = {
		'zone:plane': node( 'zone', 'P', 2, true, [ [ [ 'after', 'item:one' ] ] ] ),
		'item:one': node( 'item', 'One', 1, false, [ [ [ 'after', 'item:two' ] ] ] ),
		'item:two': node( 'item', 'Two', 1, false, [ [ [ 'after', 'item:three' ] ] ] ),
		'item:three': node( 'item', 'Three', 1, true, meatWays.map( () => [] ) )
	};
	const graph = model( payload( nodes, { maxDepth: 2 } ) );
	const view = core.overview( graph, [ 'zone:plane' ] );
	const forest = core.detailForest( graph, view );
	const one = forest.trees.get( 'zone:plane' ).visible[ 0 ].needs[ 0 ];

	assert.equal( one.state, 'expanded' );
	assert.equal( one.ways.visible[ 0 ].needs[ 0 ].state, 'limit' );
	assert.equal( forest.trees.get( 'item:three' ).visible.length, 6 );
	assert.equal( forest.trees.get( 'item:three' ).sources.length, 0 );
} );

test( 'a step beyond the depth limit belongs to the drawn step whose first way reaches it', () => {
	const nodes = {
		'zone:plane': node( 'zone', 'P', 2, true, [ [ [ 'after', 'item:one' ] ] ] ),
		'item:one': node( 'item', 'One', 1, false, [ [ [ 'after', 'item:two' ] ] ] ),
		'item:two': node( 'item', 'Two', 1, false, [ [ [ 'after', 'item:three' ] ] ] ),
		'item:three': node( 'item', 'Three', 1, true, [ [] ] )
	};
	const graph = model( payload( nodes, { maxDepth: 1 } ) );
	const view = core.overview( graph, [ 'zone:plane' ] );
	const forest = core.detailForest( graph, view );

	assert.equal( forest.owners.get( 'item:two' ), undefined );
	assert.equal( core.routeOwner( graph, view, 'item:two' ), 'zone:plane' );
	assert.equal( core.routeOwner( graph, view, 'item:three' ), 'item:three' );
} );

test( 'needs read as the text words them', () => {
	const graph = model();
	const words = ( values ) => {
		const nodes = routeNodes();
		nodes[ 'zone:plane' ].ways = [ JSON.stringify( [ values ] ) ];
		const local = model( payload( nodes ) );
		return local.ways( 'zone:plane' )[ 0 ].needs.map( ( need ) => core.needWording( local, need ) )[ 0 ];
	};

	assert.deepEqual( words( [ 'defeated', 'character:wolf', 9 ] ),
		{ lead: 'Defeat all 9 ', key: 'character:wolf', name: 'A Wolf', trail: '' } );
	assert.equal( words( [ 'defeated', 'character:wolf', 1 ] ).lead, 'Defeat ' );
	assert.equal( words( [ 'defeat', 'character:wolf' ] ).lead, 'Defeat ' );
	assert.deepEqual( words( [ 'required item', 'item:key', 2, 'L1', 'open', null, true, true, 8 ] ), {
		lead: 'required item: 2 x ',
		key: 'item:key',
		name: 'Iron Key',
		trail: ' (slot L1) (keywords: "open") (level 8) (advisory) (player access unconfirmed)'
	} );
	assert.deepEqual( words( [ 'state', null, null, null, null, 'Wait for night' ] ),
		{ lead: 'state: ', key: null, name: null, trail: 'Wait for night' } );
	assert.equal( words( [ 'standing', 'item:key', null, null, null, 'positive' ] ).trail, ' (positive)' );
	assert.equal( core.needWording( graph, graph.ways( 'quest:errand' )[ 0 ].needs[ 0 ] ).name, 'Start An Errand' );
} );

test( 'search finds every step of the data, whole names first', () => {
	const graph = model();

	assert.deepEqual( core.search( graph, '  iron  ', 10 ).map( ( entry ) => entry.key ), [ 'item:key', 'barrier:door' ] );
	assert.deepEqual( core.search( graph, 'wolf', 10 ).map( ( entry ) => entry.key ),
		[ 'item:meat', 'character:wolf' ] );
	assert.deepEqual( core.search( graph, 'the vault', 10 )[ 0 ], {
		key: 'zone:vault', name: 'The Vault', kind: 'zone', tier: 4
	} );
	assert.deepEqual( core.search( graph, 'start an', 10 ).map( ( entry ) => entry.key ), [ 'quest_start:errand' ] );
	assert.deepEqual( core.search( graph, '', 10 ), [] );
	assert.equal( core.search( graph, 'a', 2 ).length, 2 );
} );

test( 'the arrow keys reach the nearest requirement and unlock', () => {
	const graph = model();
	const view = core.overview( graph, [ 'zone:plane' ] );
	const columns = core.orderColumns( view, graph, 8 );
	const around = core.neighbours( view, columns, 'quest:ritual' );

	assert.deepEqual( around.needs, [ 'zone:vault', 'item:key', 'zone:stowaway' ] );
	assert.deepEqual( around.unlocks, [ 'zone:plane' ] );
	assert.equal( around.up, null );
	assert.equal( around.down, null );
	assert.throws( () => core.neighbours( view, columns, 'item:meat' ), /not drawn/ );
} );

test( 'kinds read as words that the reader knows', () => {
	assert.equal( core.kindLabel( 'zone' ), 'Area' );
	assert.equal( core.kindLabel( 'faction_standing' ), 'Standing' );
	assert.equal( core.kindLabel( 'new_kind' ), 'New kind' );
	assert.equal( core.tierLabel( 4 ), 'Playthrough tier 4' );
	assert.equal( core.tierLabel( null ), 'No playthrough tier recorded' );
} );
