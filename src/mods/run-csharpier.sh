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
		src/mods/*/*.cs)
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
dotnet tool restore --verbosity quiet
dotnet csharpier "${files[@]}"
