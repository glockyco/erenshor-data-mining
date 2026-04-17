#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)

if [ "$#" -eq 0 ]; then
	echo "run-csharpier.sh expects one or more repo-relative C# file paths" >&2
	exit 1
fi

mod_dirs=()

add_mod_dir() {
	local candidate="$1"
	local existing
	for existing in "${mod_dirs[@]:-}"; do
		if [ "$existing" = "$candidate" ]; then
			return
		fi
	done
	mod_dirs+=("$candidate")
}

for path in "$@"; do
	case "$path" in
		src/mods/*/*.cs)
			if [ ! -f "$repo_root/$path" ]; then
				continue
			fi
			mod_name=${path#src/mods/}
			mod_name=${mod_name%%/*}
			mod_dir="$repo_root/src/mods/$mod_name"
			tool_manifest="$mod_dir/.config/dotnet-tools.json"
			if [ ! -f "$tool_manifest" ]; then
				echo "Missing CSharpier tool manifest: $tool_manifest" >&2
				exit 1
			fi
			add_mod_dir "$mod_dir"
			;;
		*)
			echo "Unsupported path for csharpier hook: $path" >&2
			exit 1
			;;
	esac
done

for mod_dir in "${mod_dirs[@]}"; do
	mod_name=${mod_dir##*/}
	mod_files=()
	for path in "$@"; do
		case "$path" in
			src/mods/$mod_name/*)
				if [ -f "$repo_root/$path" ]; then
					mod_files+=("${path#src/mods/$mod_name/}")
				fi
				;;
		esac
	done

	if [ "${#mod_files[@]}" -eq 0 ]; then
		continue
	fi

	(
		cd "$mod_dir"
		dotnet tool restore --verbosity quiet
		dotnet csharpier "${mod_files[@]}"
	)
done
