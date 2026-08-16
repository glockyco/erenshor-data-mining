{
  lib,
  stdenvNoCC,
  fetchurl,
  makeWrapper,
  unzip,
}:

let
  version = "1.3.14";
  artifacts = {
    aarch64-darwin = {
      archive = "AssetRipper_mac_arm64.zip";
      hash = "sha256-aAiQuXxYvgIHVDiBSz9B7CqSiuC+jpT6JK1R+qgQeKo=";
    };
    x86_64-darwin = {
      archive = "AssetRipper_mac_x64.zip";
      hash = "sha256-mUimn6kFa5i/YpTA4TgU/qr8t3aHIxRzvMREiy3MT1E=";
    };
  };
  artifact = artifacts.${stdenvNoCC.hostPlatform.system};
in
stdenvNoCC.mkDerivation {
  pname = "assetripper-bin";
  inherit version;

  src = fetchurl {
    name = artifact.archive;
    url = "https://github.com/AssetRipper/AssetRipper/releases/download/${version}/${artifact.archive}";
    inherit (artifact) hash;
  };

  sourceRoot = ".";

  nativeBuildInputs = [
    makeWrapper
    unzip
  ];

  installPhase = ''
    runHook preInstall

    mkdir -p "$out/bin" "$out/lib/assetripper"
    cp -R . "$out/lib/assetripper"
    makeWrapper \
      "$out/lib/assetripper/AssetRipper.GUI.Free" \
      "$out/bin/AssetRipper" \
      --add-flags "--log=false"

    runHook postInstall
  '';

  meta = {
    description = "Tool for extracting assets from Unity serialized files and asset bundles";
    homepage = "https://github.com/AssetRipper/AssetRipper";
    license = lib.licenses.gpl3Only;
    mainProgram = "AssetRipper";
    platforms = builtins.attrNames artifacts;
    sourceProvenance = [ lib.sourceTypes.binaryNativeCode ];
  };
}
