const fs = require( 'node:fs' );
const path = require( 'node:path' );
const test = require( 'node:test' );
const vm = require( 'node:vm' );
const assert = require( 'node:assert/strict' );
const core = require( '../../../wiki/gadgets/semantic-link-picker-core.js' );

const result = ( overrides ) => Object.assign( {
	key: 'item-iron-sword',
	kind: 'item',
	subtype: 'Weapon',
	name: 'Iron Sword',
	page: 'Iron Sword',
	image: 'Iron Sword.png'
}, overrides );

const response = ( results, overrides ) => ( {
	expandtemplates: {
		wikitext: JSON.stringify( Object.assign( {
			schemaVersion: 1,
			query: 'sword',
			results: results
		}, overrides ) )
	}
} );

test( 'publishes the browser global inside a ResourceLoader module wrapper', () => {
	const context = { module: { exports: {} } };
	context.self = context;
	const source = fs.readFileSync(
		path.join( __dirname, '../../../wiki/gadgets/semantic-link-picker-core.js' ),
		'utf8'
	);

	vm.runInNewContext( source, context );

	assert.equal( typeof context.ErenshorSemanticLinkPickerCore, 'object' );
	assert.deepEqual( context.module.exports, {} );
} );

test( 'exports constants and display/query helpers', () => {
	assert.deepEqual( core.KINDS, [ 'item', 'ability', 'character', 'quest', 'zone', 'faction', 'class' ] );
	assert.equal( core.TEMPLATE_BY_KIND.item, 'ItemLink' );
	assert.equal( core.displayKind( 'zone' ), 'Zone' );
	assert.equal( core.normalizeQuery( '  Iron SWORD  ' ), 'iron sword' );
	assert.equal( core.normalizeQuery( null ), '' );
} );

test( 'validates duplicate result names and preserves records', () => {
	const results = [ result(), result( { key: 'item-steel-sword' } ) ];
	assert.deepEqual( core.validateSearchResponse( response( results ) ), results );
} );

test( 'rejects invalid response schemas and result fields', () => {
	assert.throws( () => core.validateSearchResponse( null ), /Missing expandtemplates output/ );
	assert.throws( () => core.validateSearchResponse( { expandtemplates: { wikitext: '{}' } } ), /Unsupported search schema/ );
	assert.throws( () => core.validateSearchResponse( response( [ result( { image: null } ) ] ) ), /Invalid search result field/ );
	assert.throws( () => core.validateSearchResponse( response( [ result( { extra: 'field' } ) ] ) ), /Invalid search result/ );
	assert.throws( () => core.validateSearchResponse( response( [ result( { kind: 'monster' } ) ] ) ), /Incomplete search result/ );
	assert.throws( () => core.validateSearchResponse( response( [ result( { key: '' } ) ] ) ), /Incomplete search result/ );
} );

test( 'tracks keyed metadata and resolves ambiguous keyed records deterministically', () => {
	const metadata = core.existingTargetMetadata( 'item', {
		stableKey: 'item-iron-sword',
		link: '',
		text: 'Blade'
	} );
	assert.equal( metadata.hasStableKey, true );
	assert.equal( metadata.query, 'item-iron-sword' );
	assert.equal( metadata.existingText, 'Blade' );
	assert.equal( metadata.customLabel, null );
	metadata.learnExistingRecord( [
		result( { name: 'Iron Sword' } ),
		result( { name: 'Different Name' } )
	] );
	assert.equal( metadata.customLabel, 'Blade' );
	assert.equal( metadata.labelResolved, true );

	const sameName = core.existingTargetMetadata( 'item', {
		stableKey: 'item-iron-sword',
		link: '',
		text: 'Iron Sword'
	} );
	sameName.learnExistingRecord( [ result() ] );
	assert.equal( sameName.customLabel, null );
} );

test( 'tracks unkeyed metadata and custom label overrides', () => {
	const metadata = core.existingTargetMetadata( 'item', {
		stableKey: '',
		link: 'Iron Sword',
		text: 'Blade'
	} );
	assert.equal( metadata.hasStableKey, false );
	assert.equal( metadata.query, 'Iron Sword' );
	metadata.learnExistingRecord( [ result() ] );
	assert.equal( metadata.labelResolved, false );
	metadata.resolveLabelForResult( result() );
	assert.equal( metadata.customLabel, 'Blade' );

	const unkeyedSameName = core.existingTargetMetadata( 'item', {
		stableKey: '',
		link: 'Iron Sword',
		text: 'Iron Sword'
	} );
	unkeyedSameName.resolveLabelForResult( result() );
	assert.equal( unkeyedSameName.customLabel, null );
} );

test( 'handles identity text overrides for same-name and custom labels', () => {
	const item = result();
	assert.equal( core.identityTextOverride( item, 'Iron Sword' ), null );
	assert.equal( core.identityTextOverride( item, '  ' ), null );
	assert.equal( core.identityTextOverride( item, 'Blade' ), 'Blade' );
} );

test( 'parses and rebuilds source templates while preserving unrelated nested and nowiki parameters', () => {
	const source = '{{ ItemLink | stablekey=old-key | text=Old | note={{Nested|value=a=b}} | raw=<nowiki>{{|}}</nowiki> | tail=keep}}';
	const parsed = core.parseSourceTemplate( source );
	assert.equal( parsed.kind, 'item' );
	assert.deepEqual( parsed.identity, {
		stableKey: 'old-key',
		link: '',
		text: 'Old '
	} );
	const rebuilt = core.buildSourceTemplate( parsed, result( { key: 'item-new-key' } ), 'Blade' );
	assert.equal( rebuilt, '{{ ItemLink |stablekey=item-new-key|text=Blade| note={{Nested|value=a=b}} | raw=<nowiki>{{|}}</nowiki> | tail=keep}}' );
} );

test( 'upgrades manual source templates and escapes pipe and brace identity values', () => {
	const manual = core.parseSourceTemplate( '{{ItemLink|Iron Sword|note=keep}}' );
	assert.equal( manual.identity.link, 'Iron Sword' );
	assert.equal( core.buildSourceTemplate( manual, result( { key: 'item|{key}' } ), 'Blade|{}' ),
		'{{ItemLink|stablekey=item<nowiki>|</nowiki><nowiki>{</nowiki>key<nowiki>}</nowiki>|text=Blade<nowiki>|</nowiki><nowiki>{</nowiki><nowiki>}</nowiki>|note=keep}}' );
	assert.equal( core.buildSourceTemplate( null, result(), '' ), '{{ItemLink|stablekey=item-iron-sword}}' );
} );

test( 'rejects structured selections and finds balanced source ranges', () => {
	assert.equal( core.selectionContainsStructuredWikitext( 'plain text' ), false );
	assert.equal( core.selectionContainsStructuredWikitext( 'text [[Page]]' ), true );
	const source = 'before {{ItemLink|stablekey=item-iron-sword|text=Blade}} after';
	const start = source.indexOf( '{{' );
	const end = source.indexOf( '}}' ) + 2;
	assert.deepEqual( core.findBalancedRangeAt( source, start + 12, start + 16, '{{', '}}' ), {
		start: start,
		end: end
	} );
	assert.deepEqual( core.findBalancedRangeAt( source, start, start, '{{', '}}' ), {
		start: start,
		end: end
	} );
} );

test( 'tracks opaque ranges for comments and nowiki selections', () => {
	const source = 'a<!-- hidden {{x}} -->b<nowiki>{{not a template}}</nowiki>c{{real}}';
	const tokenized = core.tokenizeSourceWindow( source, 0, source.length );
	assert.equal( tokenized.tokens.some( ( token ) => token.value === '{{' && token.start > 1 && token.start < 40 ), false );
	assert.equal( core.selectionTouchesOpaqueRange( tokenized.opaqueRanges, 3, 8 ), true );
	assert.equal( core.selectionTouchesOpaqueRange( tokenized.opaqueRanges, source.indexOf( '{{real}}' ), source.indexOf( '{{real}}' ) ), false );
	assert.equal( core.selectionTouchesOpaqueRange( tokenized.opaqueRanges, 0, 1 ), false );
} );

test( 'wraps active result indexes and handles empty results', () => {
	assert.equal( core.nextActiveIndex( -1, 3, 'ArrowDown' ), 0 );
	assert.equal( core.nextActiveIndex( -1, 3, 'ArrowUp' ), 2 );
	assert.equal( core.nextActiveIndex( 2, 3, 'ArrowDown' ), 0 );
	assert.equal( core.nextActiveIndex( 0, 3, 'ArrowUp' ), 2 );
	assert.equal( core.nextActiveIndex( 0, 0, 'ArrowDown' ), -1 );
	assert.equal( core.nextActiveIndex( 2, 0, 'ArrowUp' ), -1 );
} );

test( 'transitions selection labels for custom and user-edited values', () => {
	const results = [ result(), result( { key: 'item-steel-sword', name: 'Steel Sword' } ) ];
	assert.deepEqual( core.selectionTransition( results, 1, false, null ), {
		selectedIndex: 1,
		selectedResult: results[ 1 ],
		label: 'Steel Sword'
	} );
	assert.deepEqual( core.selectionTransition( results, 0, false, 'Favorite Blade' ), {
		selectedIndex: 0,
		selectedResult: results[ 0 ],
		label: 'Favorite Blade'
	} );
	assert.deepEqual( core.selectionTransition( results, 0, true, 'Favorite Blade' ), {
		selectedIndex: 0,
		selectedResult: results[ 0 ],
		label: null
	} );
	assert.deepEqual( core.selectionTransition( [], -1, false, null ), {
		selectedIndex: -1,
		selectedResult: null,
		label: null
	} );
} );
