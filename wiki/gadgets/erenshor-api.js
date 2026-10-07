/**
 * A GET through mw.Api that waits out wiki.gg's rate limit, shared by the Erenshor gadgets as
 * mw.libs.erenshorApi. The wiki answers a burst of API requests from one address with HTTP 429
 * and a Retry-After header. A request waits that long, at most 15 seconds, up to three times,
 * then fails like any other: the promise rejects with an Error whose code is the API's error code.
 */
( function () {
	'use strict';

	const RETRIES = 3;
	const MAX_WAIT = 15000;

	function rateLimitDelay( code, result ) {
		const xhr = result && result.xhr;
		if ( code !== 'ratelimited' && !( xhr && xhr.status === 429 ) ) {
			return null;
		}
		const seconds = Number( xhr && xhr.getResponseHeader( 'Retry-After' ) );
		return Math.min( MAX_WAIT, Number.isFinite( seconds ) && seconds > 0 ? seconds * 1000 : 2000 );
	}

	function get( api, params ) {
		return new Promise( function ( resolve, reject ) {
			function attempt( retriesLeft ) {
				api.get( params ).then( resolve, function ( code, result ) {
					const delay = rateLimitDelay( code, result );
					if ( delay !== null && retriesLeft > 0 ) {
						setTimeout( function () {
							attempt( retriesLeft - 1 );
						}, delay );
						return;
					}
					const error = new Error( 'MediaWiki API request failed: ' + code );
					error.code = code;
					reject( error );
				} );
			}
			attempt( RETRIES );
		} );
	}

	mw.libs.erenshorApi = { get: get };
}() );
