FROM mediawiki:1.43

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends git ca-certificates lua5.1; \
    rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    rm -rf \
        /var/www/html/extensions/Cargo \
        /var/www/html/extensions/CodeMirror \
        /var/www/html/extensions/Gadgets \
        /var/www/html/extensions/ParserFunctions \
        /var/www/html/extensions/PortableInfobox \
        /var/www/html/extensions/Scribunto \
        /var/www/html/extensions/TemplateData \
        /var/www/html/extensions/TemplateSandbox \
        /var/www/html/extensions/VisualEditor \
        /var/www/html/extensions/WikiEditor; \
    git clone --depth 1 --branch REL1_43 https://gerrit.wikimedia.org/r/mediawiki/extensions/Scribunto /var/www/html/extensions/Scribunto; \
    git clone --depth 1 --branch REL1_43 https://gerrit.wikimedia.org/r/mediawiki/extensions/Gadgets /var/www/html/extensions/Gadgets; \
    git clone --depth 1 --branch REL1_43 https://gerrit.wikimedia.org/r/mediawiki/extensions/ParserFunctions /var/www/html/extensions/ParserFunctions; \
    git clone --depth 1 --branch REL1_43 https://gerrit.wikimedia.org/r/mediawiki/extensions/TemplateSandbox /var/www/html/extensions/TemplateSandbox; \
    git clone --depth 1 https://gerrit.wikimedia.org/r/mediawiki/extensions/Cargo /var/www/html/extensions/Cargo; \
    git clone --depth 1 --branch REL1_43 https://gerrit.wikimedia.org/r/mediawiki/extensions/CodeMirror /var/www/html/extensions/CodeMirror; \
    git clone --depth 1 --branch REL1_43 https://gerrit.wikimedia.org/r/mediawiki/extensions/TemplateData /var/www/html/extensions/TemplateData; \
    git clone --depth 1 --branch REL1_43 --recurse-submodules https://gerrit.wikimedia.org/r/mediawiki/extensions/VisualEditor /var/www/html/extensions/VisualEditor; \
    git clone --depth 1 --branch REL1_43 https://gerrit.wikimedia.org/r/mediawiki/extensions/WikiEditor /var/www/html/extensions/WikiEditor; \
    git clone --depth 1 https://github.com/Universal-Omega/PortableInfobox.git /var/www/html/extensions/PortableInfobox

# TemplateStyles mirrors the live wiki, which runs TemplateStyles with the
# Extender. The Extender is what permits CSS custom properties and var(), so
# pages that adapt to the night and day themes through the skin's Codex tokens
# only sanitize correctly when both are present. wikimedia/css-sanitizer is
# already vendored by the base image, so neither needs composer.
RUN set -eux; \
    git clone --depth 1 --branch REL1_43 https://gerrit.wikimedia.org/r/mediawiki/extensions/TemplateStyles /var/www/html/extensions/TemplateStyles; \
    git clone --depth 1 https://github.com/octfx/mediawiki-extensions-TemplateStylesExtender.git /var/www/html/extensions/TemplateStylesExtender
