/* Local-only wiki.gg theme activation for synced MediaWiki interface CSS. */
(function () {
	document.documentElement.classList.add(
		"theme-dark",
		"view-dark",
		"skin-theme-clientpref-night"
	);
	document.body.classList.add("wgg-dom-version-1_43", "skin--responsive");
})();
