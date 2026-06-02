module.exports = {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "body-max-line-length": [2, "always", 80],
    "footer-max-line-length": [2, "always", 80],
    "header-max-length": [2, "always", 80],
    "scope-empty": [2, "never"],
    "scope-enum": [
      2,
      "always",
      [
        "cli",
        "config",
        "export",
        "guide",
        "map",
        "mod",
        "pipeline",
        "sheets",
        "test",
        "wiki",
      ],
    ],
    "subject-full-stop": [2, "never", "."],
    "type-enum": [
      2,
      "always",
      ["feat", "fix", "refactor", "style", "docs", "test", "chore"],
    ],
  },
};
