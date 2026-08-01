<?php
# Extra settings for the local Erenshor wiki development stack.
# This file is included from wiki-dev/LocalSettings.php after install.php creates it.

wfLoadSkin( 'Vector' );

wfLoadExtension( 'ParserFunctions' );
wfLoadExtension( 'Scribunto' );
wfLoadExtension( 'TemplateSandbox' );
wfLoadExtension( 'Cargo' );
wfLoadExtension( 'Gadgets' );
wfLoadExtension( 'PortableInfobox' );
wfLoadExtension( 'WikiEditor' );
wfLoadExtension( 'CodeMirror' );
wfLoadExtension( 'TemplateData' );
wfLoadExtension( 'VisualEditor' );
wfLoadExtension( 'TemplateStyles' );
wfLoadExtension( 'TemplateStylesExtender' );
# InputBox backs the create-page form on the main page. Bundled with core.
wfLoadExtension( 'InputBox' );
# NoTitle supplies __NOTITLE__ and EmbedVideo supplies <evlplayer>. Both are
# used by the main page on the live wiki, so the local preview needs them to
# render that page faithfully rather than leaking markup as literal text.
wfLoadExtension( 'NoTitle' );
wfLoadExtension( 'EmbedVideo' );


$wgScribuntoDefaultEngine = 'luastandalone';
$wgScribuntoEngineConf['luastandalone']['luaPath'] = '/usr/bin/lua5.1';

# Cargo can use the main wiki database in local development. Production wiki.gg
# uses LIBRARIAN (wiki.gg's Cargo fork), so local Cargo is a close compatibility
# layer, not an exact clone of production.
$wgCargoDBtype = $wgDBtype;
$wgCargoDBserver = $wgDBserver;
$wgCargoDBname = $wgDBname;
$wgCargoDBuser = $wgDBuser;
$wgCargoDBpassword = $wgDBpassword;

# Cargo's recreate right (recreatecargodata) stays sysop-only, matching
# production wiki.gg/LIBRARIAN where the deploy bot cannot hold it and a
# cargo-admin account performs recreation. The deploy bot is deliberately not
# granted it, so local recreation runs as the admin account (WikiSysop) and
# faithfully mirrors the production identity split.

$wgShowExceptionDetails = true;
$wgShowDBErrorBacktrace = true;

# EmbedVideo touches the service container while registering, which MediaWiki
# 1.43 reports as deprecated. The container runs with display_errors on, so the
# notice is printed into every API response and page, corrupting both. Warnings
# and errors stay visible; only deprecations are silenced.
error_reporting( E_ALL & ~E_DEPRECATED & ~E_USER_DEPRECATED );
$wgEnableUploads = true;
$wgDefaultSkin = 'vector';
$wgVectorDefaultSkinVersion = '1';
$wgMaxArticleSize = 4096;
$wgLogos = [ '1x' => '/images/Site-logo.png' ];
$wgFavicon = '/images/Site-favicon.ico';


# Show the TemplateSandbox edit box on local template and module pages.
$wgTemplateSandboxEditNamespaces = [ NS_TEMPLATE, 828 ];

$wgMaxUploadSize = 32 * 1024 * 1024;
