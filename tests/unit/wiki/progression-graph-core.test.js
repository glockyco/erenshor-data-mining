const fs = require( 'node:fs' );
const path = require( 'node:path' );
const test = require( 'node:test' );
const vm = require( 'node:vm' );
const assert = require( 'node:assert/strict' );
const core = require( '../../../wiki/gadgets/progression-graph-core.js' );

// A way in the form that Module:Erenshor/Progression puts into the payload: the
// sentence first, then one positional array per need.
const way = ( sentence, ...needs ) => JSON.stringify( [ sentence, ...needs ] );

// A vault behind a door whose key a boss drops while it rains, an errand that a
// note starts and whose reward the plane needs, and a later quest that the
// errand must leave undone.
const routeNodes = () => ( {
	'zone:start': { kind: 'zone', name: "Stowaway's Step", way: way( 'Start a new character in {zone:start}.', [ 'from', 'mechanism:start' ] ) },
	'mechanism:start': { kind: 'mechanism', name: 'New character start', page: false, way: way( 'Nothing is needed.' ) },
	'character:boss': { kind: 'character', name: 'Boss', way: way( 'Find {character:boss} in {zone:start}.', [ 'in zone', 'zone:start' ] ) },
	'world_state:rain': { kind: 'world_state', name: 'Rain in the Step', page: false, way: way( 'Wait for rain in {zone:start}.', [ 'natural weather', null, null, null, null, 'Wait for natural rain' ], [ 'in zone', 'zone:start' ] ) },
	'item:key': { kind: 'item', name: 'Iron Key', way: way( 'Defeat {character:boss} in {zone:start} for {item:key}, while it rains in {zone:start}.', [ 'drops', 'character:boss' ], [ 'release', 'world_state:rain' ] ) },
	'barrier:door': { kind: 'barrier', name: 'Iron Door', page: false, way: way( 'Open {barrier:door} with {item:key}.', [ 'key', 'item:key' ] ) },
	'zone:vault': { kind: 'zone', name: 'The Vault', way: way( 'Travel from {zone:start} to {zone:vault} through {barrier:door}.', [ 'barrier', 'barrier:door' ], [ 'zone line', 'zone:start' ] ) },
	'quest:later': { kind: 'quest', name: 'A Later Quest' },
	'item:note': { kind: 'item', name: 'A Torn Note', way: way( 'Defeat {character:boss} in {zone:start} for {item:note}.', [ 'drops', 'character:boss' ] ) },
	'quest_start:quest:errand': { kind: 'quest_start', name: 'An Errand', way: way( 'Read {item:note} to start {quest:errand}.', [ 'read', 'item:note' ] ) },
	'quest:errand': { kind: 'quest', name: 'An Errand', way: way( 'Read {item:note} to start {quest:errand}, then talk to {character:boss} in {zone:start} to finish it, before you finish {quest:later}.', [ 'talk to', 'character:boss' ], [ 'quest not done', 'quest:later' ], [ 'started', 'quest_start:quest:errand' ] ) },
	'item:reward': { kind: 'item', name: 'Errand Reward', way: way( 'Finish {quest:errand} for {item:reward}.', [ 'reward', 'quest:errand' ] ) },
	'zone:plane': { kind: 'zone', name: 'The Plane', way: way( 'Place {item:reward} on the planning table in {zone:vault} to travel to {zone:plane}.', [ 'planning slot', 'item:reward' ], [ 'zone line', 'zone:vault' ] ) }
} );

const routeChapters = () => [
	{ title: 'Unlock The Vault', parts: [ { title: 'Unlock The Vault', steps: [ 'world_state:rain', 'item:key', 'barrier:door', 'zone:vault' ] } ] },
	{ title: 'Finish An Errand', parts: [ { title: 'Finish An Errand', steps: [ 'quest:errand' ] } ] },
	{ title: 'Unlock The Plane', parts: [ { title: 'Unlock The Plane', steps: [ 'zone:plane' ] } ] }
];

const routeSteps = () => ( {
	'world_state:rain': { deps: {} },
	'item:key': { deps: [ 'world_state:rain' ] },
	'barrier:door': { deps: [ 'item:key' ] },
	'zone:vault': { deps: [ 'barrier:door' ] },
	'quest:errand': { deps: [], folds: [ 'item:reward' ] },
	'zone:plane': { deps: [ 'zone:vault', 'quest:errand' ] }
} );

const actions = {
	drops: 'defeat',
	release: 'defeat',
	'release|world_state': 'bring',
	key: 'open with',
	barrier: 'get past',
	'zone line': 'travel from',
	'planning slot': 'place',
	'talk to': 'talk to',
	'in zone': 'go to',
	reward: 'finish',
	read: 'read',
	started: 'start',
	from: 'use'
};

const payload = ( overrides ) => JSON.stringify( Object.assign( {
	targets: [ 'zone:plane' ],
	unmet: [ 'quest not done' ],
	actions: actions,
	chapters: routeChapters(),
	steps: routeSteps(),
	nodes: routeNodes()
}, overrides ) );
const model = ( text ) => core.createModel( core.parsePayload( text || payload() ) );

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

test( 'reads the route, its pages, and first ways from the payload', () => {
	const graph = model();

	assert.deepEqual( graph.order, [ 'world_state:rain', 'item:key', 'barrier:door', 'zone:vault', 'quest:errand', 'zone:plane' ] );
	assert.equal( graph.record( 'zone:vault' ).page, 'The Vault' );
	assert.equal( graph.record( 'barrier:door' ).page, null );
	// Lua writes an empty list of needs as an empty object.
	assert.deepEqual( graph.steps.get( 'world_state:rain' ).deps, [] );
	assert.deepEqual( graph.firstWay( 'item:key' ).needs[ 1 ], {
		relation: 'release',
		need: 'world_state:rain',
		quantity: null,
		slot: null,
		keywords: null,
		text: null,
		advisory: null,
		unconfirmed: null,
		requiredLevel: null
	} );
	assert.equal( graph.firstWay( 'quest:later' ), null );
} );

test( 'rejects data that the view could not have rendered', () => {
	assert.throws( () => core.parsePayload( '{"targets":' ), /cannot be read/ );
	assert.throws( () => core.parsePayload( payload( { targets: [] } ) ), /names no targets/ );
	assert.throws( () => core.parsePayload( payload( { targets: [ 'zone:start' ] } ) ), /target zone:start is no step/ );
	const missing = routeNodes();
	delete missing[ 'item:key' ];
	assert.throws( () => core.parsePayload( payload( { nodes: missing } ) ), /step item:key is missing/ );
	const steps = routeSteps();
	steps[ 'zone:vault' ].deps = [ 'zone:start' ];
	assert.throws( () => core.parsePayload( payload( { steps: steps } ) ), /names zone:start, which the route lacks/ );
	const chapters = routeChapters();
	delete chapters[ 1 ].title;
	assert.throws( () => core.parsePayload( payload( { chapters: chapters } ) ), /chapter 2 is malformed/ );
	const broken = routeNodes();
	broken[ 'item:key' ].way = JSON.stringify( [ [ 'drops', 'character:boss' ] ] );
	assert.throws( () => model( payload( { nodes: broken } ) ).firstWay( 'item:key' ), /has no sentence/ );
} );

test( 'a goal keeps its step and every step that it needs', () => {
	const graph = model();

	assert.deepEqual( [ ...core.goalSteps( graph, 'zone:vault' ) ].sort(), [ 'barrier:door', 'item:key', 'world_state:rain', 'zone:vault' ] );
	assert.equal( core.goalSteps( graph, 'zone:plane' ).size, 6 );
	// A reward that a quest's step names leads to that quest.
	assert.deepEqual( [ ...core.goalSteps( graph, 'item:reward' ) ], [ 'quest:errand' ] );
	assert.throws( () => core.goalSteps( graph, 'quest:later' ), /not on this route/ );
} );

test( 'transitive reduction drops a line that a longer path already implies', () => {
	assert.deepEqual(
		core.transitiveReduction( 4, [ { from: 0, to: 1 }, { from: 1, to: 2 }, { from: 0, to: 2 }, { from: 2, to: 3 }, { from: 0, to: 3 } ] ),
		[ { from: 0, to: 1 }, { from: 1, to: 2 }, { from: 2, to: 3 } ]
	);
} );

test( 'the chapter graph holds the chapters of the goal and how they depend on each other', () => {
	const graph = model();
	const plane = core.chapterGraph( graph, core.goalSteps( graph, 'zone:plane' ) );
	const vault = core.chapterGraph( graph, core.goalSteps( graph, 'zone:vault' ) );

	assert.deepEqual( plane.chapters.map( ( chapter ) => chapter.title ), [ 'Unlock The Vault', 'Finish An Errand', 'Unlock The Plane' ] );
	assert.deepEqual( plane.edges, [ { from: 0, to: 2 }, { from: 1, to: 2 } ] );
	assert.deepEqual( vault.chapters.map( ( chapter ) => [ chapter.chapter, chapter.steps.length ] ), [ [ 0, 4 ] ] );
	assert.deepEqual( vault.edges, [] );
} );

test( 'a line that spans layers bends through a place of its own in each layer it crosses', () => {
	const size = { width: 100, height: 40, gapX: 20, gapY: 30, bend: 10 };
	// A then B then C, and D, which needs nothing, is a requirement of C.
	const graph = {
		chapters: [ 'A', 'B', 'C', 'D' ].map( ( title, index ) => ( { chapter: index, title: title, steps: [ title ] } ) ),
		edges: [ { from: 0, to: 1 }, { from: 1, to: 2 }, { from: 3, to: 2 } ]
	};
	const layout = core.layoutChapters( graph, size );
	const card = ( index ) => layout.cards[ index ];
	const long = layout.lines.find( ( line ) => line.from === 3 );

	assert.deepEqual( layout.cards.map( ( place ) => place.y ), [ 0, 70, 140, 0 ] );
	assert.equal( long.points.length, 3 );
	// The bend lies in the middle layer, beside B rather than through it.
	assert.equal( long.points[ 1 ].y, 70 + 20 );
	assert.ok( long.points[ 1 ].x < card( 1 ).x || long.points[ 1 ].x > card( 1 ).x + card( 1 ).width );
	for ( const line of layout.lines ) {
		for ( let index = 1; index < line.points.length; index++ ) {
			assert.ok( line.points[ index ].y > line.points[ index - 1 ].y, 'a line runs down' );
		}
	}
	assert.equal( layout.height, 3 * 40 + 2 * 30 );
	assert.match( core.linePath( long.points ), /^M\S+ \S+ C/ );
} );

test( 'a neighbourhood shows what a node needs and what needs it, with the action of each line', () => {
	const graph = model();
	const key = core.neighbourhood( graph, 'item:key' );
	const errand = core.neighbourhood( graph, 'quest:errand' );

	assert.deepEqual( key.needs, [ { key: 'character:boss', action: 'defeat' }, { key: 'world_state:rain', action: 'bring' } ] );
	assert.deepEqual( key.unlocks, [ { key: 'barrier:door', action: 'open with' } ] );
	// A quest to keep undone is no requirement, so neither side names the other.
	// The note that starts the errand counts as the errand's own need.
	assert.deepEqual( errand.needs, [ { key: 'character:boss', action: 'talk to' }, { key: 'item:note', action: 'read' } ] );
	assert.deepEqual( core.neighbourhood( graph, 'item:note' ).unlocks, [ { key: 'quest:errand', action: 'read' } ] );
	assert.deepEqual( core.neighbourhood( graph, 'quest:later' ).unlocks, [] );
	assert.deepEqual( core.neighbourhood( graph, 'quest:errand' ).unlocks, [ { key: 'item:reward', action: 'finish' } ] );
} );

test( 'a neighbourhood lays out its needs, the node, and what needs it from left to right', () => {
	const size = { width: 100, height: 40, gapX: 60, gapY: 10 };
	const near = {
		key: 'center',
		needs: [ { key: 'a', action: 'defeat' }, { key: 'b', action: 'bring' } ],
		unlocks: [ { key: 'c', action: 'use' }, { key: 'd', action: 'go to' }, { key: 'e', action: 'use' } ]
	};
	const layout = core.layoutNeighbourhood( near, size );
	const cards = [ ...layout.needs, layout.center, ...layout.unlocks ];
	const gaps = [ [ 100, 160 ], [ 260, 320 ] ];

	// The cards of one action stay together, in the order of their first card.
	assert.deepEqual( cards.map( ( card ) => [ card.key, card.x, card.y ] ), [
		[ 'a', 0, 25 ], [ 'b', 0, 75 ], [ 'center', 160, 50 ], [ 'c', 320, 0 ], [ 'e', 320, 50 ], [ 'd', 320, 100 ]
	] );
	assert.deepEqual( [ layout.width, layout.height ], [ 420, 140 ] );
	// Each action's label sits at the fork of its lines, in the middle of a gap.
	assert.deepEqual( layout.groups.map( ( group ) => [ group.action, group.fork.x, group.fork.y ] ), [
		[ 'defeat', 130, 45 ], [ 'bring', 130, 95 ], [ 'use', 290, 45 ], [ 'go to', 290, 120 ]
	] );
	for ( const group of layout.groups ) {
		for ( const path of group.paths ) {
			assert.ok( gaps.some( ( [ left, right ] ) => left <= path.from.x && path.from.x < path.to.x && path.to.x <= right ),
				'a line runs rightwards within one gap' );
		}
	}
	assert.deepEqual( layout.arrows, [ { x: 160, y: 70 }, { x: 320, y: 20 }, { x: 320, y: 70 }, { x: 320, y: 120 } ] );
	// Without needs the node starts the row.
	const alone = core.layoutNeighbourhood( { key: 'center', needs: [], unlocks: [ { key: 'c', action: 'use' } ] }, size );
	assert.deepEqual( [ alone.center.x, alone.unlocks[ 0 ].x, alone.width ], [ 0, 160, 260 ] );
	// A path leaves and meets its ends horizontally, which the arrows assume.
	assert.equal( core.sidewaysPath( { x: 0, y: 0 }, { x: 60, y: 20 } ), 'M0 0 C30 0 30 20 60 20' );
} );

test( 'a node that is no step belongs to the nearest step whose first way leads to it', () => {
	const graph = model();

	assert.equal( graph.owner( 'item:key' ), 'item:key' );
	assert.equal( graph.owner( 'item:reward' ), 'quest:errand' );
	// The boss drops the key and receives the errand, and the key comes first.
	assert.equal( graph.owner( 'character:boss' ), 'item:key' );
	assert.equal( graph.owner( 'zone:start' ), 'world_state:rain' );
	assert.equal( graph.owner( 'quest:later' ), null );
} );

test( 'search finds the route by name, whole names first and then in route order', () => {
	const graph = model();

	assert.deepEqual( core.search( graph, '  iron  ', 10 ).map( ( entry ) => entry.key ), [ 'item:key', 'barrier:door' ] );
	assert.deepEqual( core.search( graph, 'the vault', 10 ).map( ( entry ) => entry.key ), [ 'zone:vault' ] );
	assert.deepEqual( core.search( graph, 'reward', 10 ), [
		{ key: 'item:reward', name: 'Errand Reward', kind: 'item', owner: 'quest:errand', rank: 2 }
	] );
	// A quest that no step leads to is not part of this route, and a quest's
	// start, which carries the quest's name, is found as the quest.
	assert.deepEqual( core.search( graph, 'later', 10 ), [] );
	assert.deepEqual( core.search( graph, 'errand', 10 ).map( ( entry ) => entry.key ), [ 'item:reward', 'quest:errand' ] );
	assert.deepEqual( core.search( graph, ' ', 10 ), [] );
} );

test( 'a sentence splits into its text and the nodes that it names', () => {
	const graph = model();

	assert.deepEqual( core.sentenceParts( graph, graph.firstWay( 'barrier:door' ).sentence ), [
		{ text: 'Open ' },
		{ key: 'barrier:door', name: 'Iron Door', page: null },
		{ text: ' with ' },
		{ key: 'item:key', name: 'Iron Key', page: 'Iron Key' },
		{ text: '.' }
	] );
} );
