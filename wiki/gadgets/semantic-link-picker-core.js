( function ( root, factory ) {
	const core = factory();
	if ( typeof process === 'object' && process.versions && process.versions.node &&
		typeof module === 'object' && module.exports ) {
		module.exports = core;
	} else {
		root.ErenshorSemanticLinkPickerCore = core;
	}
}( typeof self !== 'undefined' ? self : typeof globalThis !== 'undefined' ? globalThis : this, function () {
	'use strict';

	const MAX_SOURCE_SCAN = 20000;
	const OPAQUE_TAGS = new Set( [
		'nowiki', 'ref', 'pre', 'syntaxhighlight', 'source', 'math', 'gallery', 'poem', 'code'
	] );
	const RESULT_FIELDS = [ 'key', 'kind', 'subtype', 'name', 'page', 'image' ];
	const KINDS = [ 'item', 'ability', 'character', 'quest', 'zone', 'faction', 'class' ];
	const TEMPLATE_BY_KIND = {
		item: 'ItemLink',
		ability: 'AbilityLink',
		character: 'CharacterLink',
		quest: 'QuestLink',
		zone: 'ZoneLink',
		faction: 'FactionLink',
		class: 'ClassLink'
	};
	const KIND_BY_TEMPLATE = KINDS.reduce( function ( kinds, kind ) {
		kinds[ ( 'Template:' + TEMPLATE_BY_KIND[ kind ] ).toLowerCase() ] = kind;
		kinds[ TEMPLATE_BY_KIND[ kind ].toLowerCase() ] = kind;
		return kinds;
	}, {} );

	function displayKind( kind ) {
		return kind.charAt( 0 ).toUpperCase() + kind.slice( 1 );
	}

	function normalizeQuery( value ) {
		return String( value || '' ).trim().toLowerCase();
	}

	function selectionContainsStructuredWikitext( value ) {
		return value.indexOf( '{{' ) !== -1 || value.indexOf( '}}' ) !== -1 ||
			value.indexOf( '[[' ) !== -1 || value.indexOf( ']]' ) !== -1;
	}

	function tokenizeSourceWindow( text, selectionStart, selectionEnd ) {
		const windowStart = Math.max( 0, selectionStart - MAX_SOURCE_SCAN );
		const windowEnd = Math.min( text.length, Math.max( selectionStart, selectionEnd ) + MAX_SOURCE_SCAN );
		const tokenized = tokenizeWikitext( text, 0 );
		return {
			tokens: tokenized.tokens.filter( function ( token ) {
				return token.start >= windowStart && token.start < windowEnd;
			} ),
			opaqueRanges: tokenized.opaqueRanges
		};
	}

	function selectionTouchesOpaqueRange( opaqueRanges, selectionStart, selectionEnd ) {
		return opaqueRanges.some( function ( range ) {
			if ( selectionStart === selectionEnd ) {
				return selectionStart >= range.start && selectionStart < range.end;
			}
			return selectionStart < range.end && selectionEnd > range.start;
		} );
	}

	function findBalancedRangeAt( text, selectionStart, selectionEnd, openToken, closeToken, tokenized ) {
		const sourceTokens = tokenized || tokenizeSourceWindow( text, selectionStart, selectionEnd );
		const structuralTokens = sourceTokens.tokens.filter( function ( token ) {
			return token.value === openToken || token.value === closeToken;
		} );
		let openingIndex = structuralTokens.findIndex( function ( token ) {
			return token.value === openToken && token.start === selectionStart;
		} );
		const immediatelyAfterClose = structuralTokens.some( function ( token ) {
			return token.value === closeToken && token.end === selectionStart;
		} );

		if ( openingIndex === -1 ) {
			let depth = 0;
			for ( let index = structuralTokens.length - 1; index >= 0; index-- ) {
				const token = structuralTokens[ index ];
				if ( token.start >= selectionStart ) {
					continue;
				}
				if ( token.value === closeToken ) {
					depth++;
					continue;
				}
				if ( depth === 0 ) {
					openingIndex = index;
					break;
				}
				depth--;
				if ( immediatelyAfterClose && depth === 0 ) {
					openingIndex = index;
					break;
				}
			}
		}

		if ( openingIndex === -1 ) {
			return null;
		}

		let depth = 0;
		const opening = structuralTokens[ openingIndex ];
		for ( let index = openingIndex; index < structuralTokens.length; index++ ) {
			const token = structuralTokens[ index ];
			if ( token.start - opening.start > MAX_SOURCE_SCAN ) {
				return null;
			}
			if ( token.value === openToken ) {
				depth++;
			} else {
				depth--;
				if ( depth === 0 ) {
					if ( selectionStart >= opening.start && selectionEnd <= token.end ) {
						return { start: opening.start, end: token.end };
					}
					return null;
				}
			}
		}
		return null;
	}

	function parseSourceTemplate( wikitext ) {
		if ( wikitext.slice( 0, 2 ) !== '{{' || wikitext.slice( -2 ) !== '}}' ) {
			return null;
		}

		const segments = splitTopLevel( wikitext.slice( 2, -2 ), '|' );
		const nameSegment = segments.shift();
		const kind = kindForTemplate( nameSegment );
		if ( !kind ) {
			return null;
		}

		let positionalIndex = 0;
		const params = segments.map( function ( segment ) {
			const equalsIndex = findTopLevelCharacter( segment, '=' );
			if ( equalsIndex === -1 ) {
				positionalIndex++;
				return {
					raw: '|' + segment,
					name: String( positionalIndex ),
					value: segment,
					positional: true
				};
			}
			return {
				raw: '|' + segment,
				name: segment.slice( 0, equalsIndex ).trim(),
				value: segment.slice( equalsIndex + 1 ),
				positional: false
			};
		} );

		return {
			kind: kind,
			nameSegment: nameSegment,
			params: params,
			identity: identityFromParameters( params, kind )
		};
	}

	function splitTopLevel( value, delimiter ) {
		const segments = [];
		const tokenized = tokenizeWikitext( value, 0 );
		let start = 0;
		let curlyDepth = 0;
		let squareDepth = 0;
		tokenized.tokens.forEach( function ( token ) {
			if ( token.value === '{{' ) {
				curlyDepth++;
			} else if ( token.value === '}}' && curlyDepth > 0 ) {
				curlyDepth--;
			} else if ( token.value === '[[' ) {
				squareDepth++;
			} else if ( token.value === ']]' && squareDepth > 0 ) {
				squareDepth--;
			} else if ( token.value === delimiter && curlyDepth === 0 && squareDepth === 0 ) {
				segments.push( value.slice( start, token.start ) );
				start = token.end;
			}
		} );
		segments.push( value.slice( start ) );
		return segments;
	}

	function findTopLevelCharacter( value, character ) {
		const tokenized = tokenizeWikitext( value, 0 );
		let curlyDepth = 0;
		let squareDepth = 0;
		for ( let index = 0; index < tokenized.tokens.length; index++ ) {
			const token = tokenized.tokens[ index ];
			if ( token.value === '{{' ) {
				curlyDepth++;
			} else if ( token.value === '}}' && curlyDepth > 0 ) {
				curlyDepth--;
			} else if ( token.value === '[[' ) {
				squareDepth++;
			} else if ( token.value === ']]' && squareDepth > 0 ) {
				squareDepth--;
			} else if ( token.value === character && curlyDepth === 0 && squareDepth === 0 ) {
				return token.start;
			}
		}
		return -1;
	}

	function tokenizeWikitext( value, offset ) {
		const tokens = [];
		const opaqueRanges = [];
		let index = 0;
		while ( index < value.length ) {
			if ( value.slice( index, index + 4 ) === '<!--' ) {
				const commentEnd = value.indexOf( '-->', index + 4 );
				const end = commentEnd === -1 ? value.length : commentEnd + 3;
				opaqueRanges.push( { start: offset + index, end: offset + end } );
				index = end;
				continue;
			}

			const tag = readWikitextTag( value, index );
			if ( tag && OPAQUE_TAGS.has( tag.name ) ) {
				let end = tag.end;
				if ( !tag.closing && !tag.selfClosing ) {
					end = findOpaqueTagEnd( value, tag );
				}
				opaqueRanges.push( { start: offset + index, end: offset + end } );
				index = end;
				continue;
			}

			const pair = value.slice( index, index + 2 );
			if ( pair === '{{' || pair === '}}' || pair === '[[' || pair === ']]' ) {
				tokens.push( { value: pair, start: offset + index, end: offset + index + 2 } );
				index += 2;
				continue;
			}
			const character = value.charAt( index );
			if ( character === '|' || character === '=' ) {
				tokens.push( { value: character, start: offset + index, end: offset + index + 1 } );
			}
			index++;
		}
		return { tokens: tokens, opaqueRanges: opaqueRanges };
	}

	function readWikitextTag( value, start ) {
		if ( value.charAt( start ) !== '<' ) {
			return null;
		}
		let index = start + 1;
		let closing = false;
		while ( /\s/.test( value.charAt( index ) ) ) {
			index++;
		}
		if ( value.charAt( index ) === '/' ) {
			closing = true;
			index++;
			while ( /\s/.test( value.charAt( index ) ) ) {
				index++;
			}
		}
		const nameStart = index;
		while ( /[A-Za-z0-9]/.test( value.charAt( index ) ) ) {
			index++;
		}
		if ( index === nameStart ) {
			return null;
		}
		const name = value.slice( nameStart, index ).toLowerCase();
		let quote = '';
		for ( ; index < value.length; index++ ) {
			const character = value.charAt( index );
			if ( quote ) {
				if ( character === quote ) {
					quote = '';
				}
				continue;
			}
			if ( character === '"' || character === "'" ) {
				quote = character;
				continue;
			}
			if ( character === '>' ) {
				let previous = index - 1;
				while ( previous > start && /\s/.test( value.charAt( previous ) ) ) {
					previous--;
				}
				return {
					name: name,
					closing: closing,
					selfClosing: value.charAt( previous ) === '/',
					start: start,
					end: index + 1
				};
			}
		}
		return null;
	}

	function findOpaqueTagEnd( value, openingTag ) {
		const lowerValue = value.toLowerCase();
		const closePrefix = '</' + openingTag.name;
		let candidate = lowerValue.indexOf( closePrefix, openingTag.end );
		while ( candidate !== -1 ) {
			const closingTag = readWikitextTag( value, candidate );
			if ( closingTag && closingTag.closing && closingTag.name === openingTag.name ) {
				return closingTag.end;
			}
			candidate = lowerValue.indexOf( closePrefix, candidate + closePrefix.length );
		}
		return value.length;
	}

	function normalizedTemplateName( value ) {
		return String( value || '' )
			.replace( /_/g, ' ' )
			.trim()
			.replace( /\s+/g, ' ' )
			.toLowerCase();
	}

	function kindForTemplate( value ) {
		return KIND_BY_TEMPLATE[ normalizedTemplateName( value ) ] || null;
	}

	function identityFromParameters( params, kind ) {
		const identity = {
			stableKey: '',
			link: '',
			text: ''
		};
		params.forEach( function ( param ) {
			const name = param.name.toLowerCase();
			const value = param.value;
			if ( !identity.stableKey && [ 'stablekey', 'key' ].indexOf( name ) !== -1 ) {
				identity.stableKey = value.trim();
			} else if ( !identity.link && [ 'link', 'page' ].indexOf( name ) !== -1 ) {
				identity.link = value.trim();
			} else if ( !identity.text && name === 'text' ) {
				identity.text = value;
			} else if ( !identity.link && sourceParameterIsManualTarget( param, kind ) ) {
				identity.link = value.trim();
			}
		} );
		return identity;
	}

	function sourceParameterIsManualTarget( param, kind ) {
		const name = param.name.toLowerCase();
		return name === '1' || kind === 'item' && [ 'item', 'name' ].indexOf( name ) !== -1;
	}

	function sourceParameterIsIdentity( param, kind ) {
		const name = param.name.toLowerCase();
		return [ 'stablekey', 'key', 'link', 'page', 'text', 'image' ].indexOf( name ) !== -1 ||
			sourceParameterIsManualTarget( param, kind );
	}

	function buildSourceTemplate( parsed, result, label ) {
		const templateName = TEMPLATE_BY_KIND[ result.kind ];
		const identity = sourceIdentityWikitext( result, label );
		if ( !parsed ) {
			return '{{' + templateName + identity + '}}';
		}

		const leadingWhitespace = parsed.nameSegment.match( /^\s*/ )[ 0 ];
		const trailingWhitespace = parsed.nameSegment.match( /\s*$/ )[ 0 ];
		let identityWritten = false;
		let params = '';
		parsed.params.forEach( function ( param ) {
			if ( sourceParameterIsIdentity( param, parsed.kind ) ) {
				if ( !identityWritten ) {
					params += identity;
					identityWritten = true;
				}
				return;
			}
			params += param.raw;
		} );
		if ( !identityWritten ) {
			params = identity + params;
		}
		return '{{' + leadingWhitespace + templateName + trailingWhitespace + params + '}}';
	}

	function sourceIdentityWikitext( result, label ) {
		let output = '|stablekey=' + serializeSourceIdentityValue( result.key );
		const text = identityTextOverride( result, label );
		if ( text !== null ) {
			output += '|text=' + serializeSourceIdentityValue( text );
		}
		return output;
	}

	function identityTextOverride( result, label ) {
		const text = String( label || '' );
		return text.trim() && text !== result.name ? text : null;
	}

	function serializeSourceIdentityValue( value ) {
		return String( value ).replace( /[|{}]/g, function ( character ) {
			return '<nowiki>' + character + '</nowiki>';
		} );
	}

	function existingTargetMetadata( kind, identity ) {
		const metadata = {
			hasStableKey: Boolean( identity.stableKey ),
			query: identity.stableKey || identity.link || identity.text,
			existingText: identity.text || null,
			customLabel: null,
			labelResolved: !identity.text,
			identity: identity
		};
		metadata.learnExistingRecord = function ( results ) {
			if ( this.labelResolved || !this.existingText || !identity.stableKey ) {
				return;
			}
			const existing = results.find( function ( result ) {
				return result.key === identity.stableKey;
			} );
			if ( existing ) {
				this.customLabel = this.existingText === existing.name ? null : this.existingText;
				this.labelResolved = true;
			}
		};
		metadata.resolveLabelForResult = function ( result ) {
			if ( !this.existingText || identity.stableKey && this.labelResolved ) {
				return;
			}
			if ( identity.stableKey && result.key !== identity.stableKey ) {
				this.customLabel = this.existingText;
			} else {
				this.customLabel = this.existingText === result.name ? null : this.existingText;
			}
			if ( identity.stableKey ) {
				this.labelResolved = true;
			}
		};
		return metadata;
	}

	function validateSearchResponse( response ) {
		if ( !response || !response.expandtemplates ||
			typeof response.expandtemplates.wikitext !== 'string' ) {
			throw new Error( 'Missing expandtemplates output' );
		}
		const payload = JSON.parse( response.expandtemplates.wikitext );
		if ( !payload || payload.schemaVersion !== 1 || typeof payload.query !== 'string' ||
			!Array.isArray( payload.results ) ) {
			throw new Error( 'Unsupported search schema' );
		}
		return payload.results.map( function ( result ) {
			if ( !result || Object.keys( result ).sort().join( '\u0000' ) !==
				RESULT_FIELDS.slice().sort().join( '\u0000' ) ) {
				throw new Error( 'Invalid search result' );
			}
			RESULT_FIELDS.forEach( function ( field ) {
				if ( typeof result[ field ] !== 'string' ) {
					throw new Error( 'Invalid search result field' );
				}
			} );
			if ( KINDS.indexOf( result.kind ) === -1 || !result.key || !result.name || !result.page ) {
				throw new Error( 'Incomplete search result' );
			}
			return result;
		} );
	}

	function nextActiveIndex( current, count, direction ) {
		if ( count <= 0 ) {
			return -1;
		}
		if ( current === -1 ) {
			return direction === 'ArrowDown' ? 0 : count - 1;
		}
		const delta = direction === 'ArrowDown' ? 1 : -1;
		return ( current + delta + count ) % count;
	}

	function selectionTransition( results, index, labelUserEdited, customLabel ) {
		const selectedResult = results[ index ] || null;
		return {
			selectedIndex: index,
			selectedResult: selectedResult,
			label: labelUserEdited ? null : customLabel !== null ? customLabel : selectedResult ? selectedResult.name : null
		};
	}

	return {
		KINDS: KINDS,
		TEMPLATE_BY_KIND: TEMPLATE_BY_KIND,
		displayKind: displayKind,
		normalizeQuery: normalizeQuery,
		selectionContainsStructuredWikitext: selectionContainsStructuredWikitext,
		tokenizeSourceWindow: tokenizeSourceWindow,
		selectionTouchesOpaqueRange: selectionTouchesOpaqueRange,
		findBalancedRangeAt: findBalancedRangeAt,
		parseSourceTemplate: parseSourceTemplate,
		buildSourceTemplate: buildSourceTemplate,
		identityTextOverride: identityTextOverride,
		existingTargetMetadata: existingTargetMetadata,
		validateSearchResponse: validateSearchResponse,
		nextActiveIndex: nextActiveIndex,
		selectionTransition: selectionTransition,
		kindForTemplate: kindForTemplate,
		identityFromParameters: identityFromParameters
	};
} ) );
