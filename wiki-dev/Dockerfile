FROM mediawiki:1.43

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends git ca-certificates lua5.1; \
    rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    rm -rf \
        /var/www/html/extensions/Cargo \
        /var/www/html/extensions/Gadgets \
        /var/www/html/extensions/ParserFunctions \
        /var/www/html/extensions/Scribunto \
        /var/www/html/extensions/TemplateSandbox; \
    git clone --depth 1 --branch REL1_43 https://gerrit.wikimedia.org/r/mediawiki/extensions/Scribunto /var/www/html/extensions/Scribunto; \
    git clone --depth 1 --branch REL1_43 https://gerrit.wikimedia.org/r/mediawiki/extensions/Gadgets /var/www/html/extensions/Gadgets; \
    git clone --depth 1 --branch REL1_43 https://gerrit.wikimedia.org/r/mediawiki/extensions/ParserFunctions /var/www/html/extensions/ParserFunctions; \
    git clone --depth 1 --branch REL1_43 https://gerrit.wikimedia.org/r/mediawiki/extensions/TemplateSandbox /var/www/html/extensions/TemplateSandbox; \
    git clone --depth 1 https://gerrit.wikimedia.org/r/mediawiki/extensions/Cargo /var/www/html/extensions/Cargo
