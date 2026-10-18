#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)

if [ "$#" -eq 0 ]; then
	# No C# files to format (e.g. a deletion-only commit, where lefthook
	# filters out the removed paths). Nothing to do.
	exit 0
fi

tool_manifest="$repo_root/.config/dotnet-tools.json"
if [ ! -f "$tool_manifest" ]; then
	echo "Missing CSharpier tool manifest: $tool_manifest" >&2
	exit 1
fi

files=()
for path in "$@"; do
	case "$path" in
		*.cs)
			if [ -f "$repo_root/$path" ]; then
				files+=("$path")
			fi
			;;
		*)
			echo "Unsupported path for csharpier hook: $path" >&2
			exit 1
			;;
	esac
done

if [ "${#files[@]}" -eq 0 ]; then
	exit 0
fi

cd "$repo_root"
# The hook wraps this script in `bash`, which the wrapper finds on any PATH, so
# dotnet itself must be the command that the wrapper probes.
scripts/with-dev-env.sh dotnet tool restore --verbosity quiet
scripts/with-dev-env.sh dotnet csharpier format "${files[@]}"
