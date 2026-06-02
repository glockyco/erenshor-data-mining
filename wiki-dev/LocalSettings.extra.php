<?php
# Extra settings for the local Erenshor wiki development stack.
# This file is included from wiki-dev/LocalSettings.php after install.php creates it.

wfLoadExtension( 'ParserFunctions' );
wfLoadExtension( 'Scribunto' );
wfLoadExtension( 'TemplateSandbox' );
wfLoadExtension( 'Cargo' );

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

# Let TemplateSandbox appear broadly in the local dev wiki.
$wgTemplateSandboxEditNamespaces = true;
