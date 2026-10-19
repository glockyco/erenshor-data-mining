/**
 * Loads the progression graph only on pages that hold its container.
 */
( function () {
	'use strict';

	const SELECTOR = '.erenshor-progression-graph[data-erenshor-progression]';

	mw.hook( 'wikipage.content' ).add( function ( $content ) {
		if ( $content.find( SELECTOR ).addBack( SELECTOR ).length ) {
			mw.loader.load( 'ext.gadget.progression-graph' );
		}
	} );
}() );
