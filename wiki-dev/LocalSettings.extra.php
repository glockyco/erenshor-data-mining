<?php
# Extra settings for the local Erenshor wiki development stack.
# This file is included from wiki-dev/LocalSettings.php after install.php creates it.

wfLoadSkin( 'Vector' );

wfLoadExtension( 'ParserFunctions' );
wfLoadExtension( 'Scribunto' );
wfLoadExtension( 'TemplateSandbox' );
wfLoadExtension( 'Cargo' );
wfLoadExtension( 'Gadgets' );


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

$wgShowExceptionDetails = true;
$wgShowDBErrorBacktrace = true;
$wgEnableUploads = true;
$wgDefaultSkin = 'vector';
$wgVectorDefaultSkinVersion = '1';
$wgMaxArticleSize = 4096;
$wgLogos = [ '1x' => '/images/Site-logo.png' ];
$wgFavicon = '/images/Site-favicon.ico';


# Show the TemplateSandbox edit box on local template and module pages.
$wgTemplateSandboxEditNamespaces = [ NS_TEMPLATE, 828 ];
