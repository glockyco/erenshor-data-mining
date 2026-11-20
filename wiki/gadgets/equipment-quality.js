( function () {
	'use strict';

	const storageKey = 'erenshor-equipment-quality';
	let nextSet = 0;

	function addQualityTabs( set ) {
		if ( set.classList.contains( 'erenshor-quality-tabs' ) ) {
			return;
		}
		const panels = Array.from( set.children ).filter( ( child ) => child.hasAttribute( 'data-erenshor-quality' ) );
		if ( panels.length < 2 ) {
			return;
		}

		const qualities = panels.map( ( panel ) => panel.getAttribute( 'data-erenshor-quality' ) );
		const standard = Math.max( 0, qualities.indexOf( 'Standard' ) );
		const name = panels[ standard ].querySelector( '.item-tooltip-name' );
		const list = document.createElement( 'div' );
		const id = 'erenshor-quality-' + ( ++nextSet ) + '-';
		list.className = 'erenshor-quality-tablist';
		list.setAttribute( 'role', 'tablist' );
		list.setAttribute( 'aria-label', ( name ? name.textContent.trim() : 'Equipment' ) + ' quality' );

		const tabs = panels.map( function ( panel, index ) {
			const tab = document.createElement( 'button' );
			tab.type = 'button';
			tab.id = id + 'tab-' + index;
			tab.textContent = qualities[ index ];
			tab.setAttribute( 'role', 'tab' );
			panel.id = id + 'panel-' + index;
			panel.setAttribute( 'role', 'tabpanel' );
			panel.setAttribute( 'aria-labelledby', tab.id );
			panel.tabIndex = 0;
			tab.setAttribute( 'aria-controls', panel.id );
			list.append( tab );
			return tab;
		} );

		function select( index, remember ) {
			tabs.forEach( function ( tab, i ) {
				const active = i === index;
				tab.setAttribute( 'aria-selected', String( active ) );
				tab.tabIndex = active ? 0 : -1;
				panels[ i ].hidden = !active;
			} );
			if ( remember ) {
				mw.storage.set( storageKey, qualities[ index ] );
			}
		}

		tabs.forEach( function ( tab, i ) {
			tab.addEventListener( 'click', () => select( i, true ) );
			tab.addEventListener( 'keydown', function ( event ) {
				let index;
				switch ( event.key ) {
					case 'ArrowLeft':
					case 'ArrowRight': {
						const rtl = getComputedStyle( list ).direction === 'rtl';
						const step = ( event.key === 'ArrowRight' ) !== rtl ? 1 : -1;
						index = ( i + step + tabs.length ) % tabs.length;
						break;
					}
					case 'Home':
						index = 0;
						break;
					case 'End':
						index = tabs.length - 1;
						break;
					default:
						return;
				}
				event.preventDefault();
				select( index, true );
				tabs[ index ].focus();
			} );
		} );

		const saved = qualities.indexOf( mw.storage.get( storageKey ) );
		select( saved < 0 ? standard : saved, false );
		set.prepend( list );
		set.classList.add( 'erenshor-quality-tabs' );
	}

	mw.hook( 'wikipage.content' ).add( function ( $content ) {
		$content[ 0 ].querySelectorAll( '.item-tooltip-quality-set' ).forEach( addQualityTabs );
	} );
}() );
