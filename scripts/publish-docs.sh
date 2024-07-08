#!/usr/bin/env bash

set -e

IFS=', ' read -r -a VERSIONS <<< "$1"
echo "versions: ${VERSIONS}"

# GNU prefix command for mac os support (gsed, gsplit)
GP=
if [[ "$OSTYPE" =~ darwin* ]]; then
  GP=g
fi

echo "Current dir: $(pwd)"


echo "*** Create publish directory"
mkdir -p "publish"
rm -rf publish/*
pushd publish

echo "*** Clone gh-pages branch"
OUTPUT=${QGIS_VERSION}
if [[ -n ${GITHUB_RUN_ID} ]]; then
  git config --global user.email "qgisninja@gmail.com"
  git config --global user.name "Geo-Ninja"
  git clone https://${GH_TOKEN}@github.com/qgis/pyqgis.git --depth 1 --branch gh-pages
else
  git clone git@github.com:qgis/pyqgis.git --depth 1 --branch gh-pages
fi
pushd pyqgis

for VERSION in "${VERSIONS[@]}"; do
  echo "get ${VERSION}"
  rm -rf ${VERSION}
  mkdir "${VERSION}"
  cp -R ../../${VERSION}/html/* ${VERSION}/
done

echo "##[group] Git commit"
echo "*** Add and push"
git add --all
git commit -m "Update docs"
echo "##[endgroup]"
if [[ -n ${GITHUB_RUN_ID} ]]; then
  echo "pushing from CI without confirmation"
  git push -f
else
  read -p "Are you sure to push? (y/n)" -n 1 -r response
  echo    # (optional) move to a new line
  if [[ $response =~ ^[Yy](es)?$ ]]; then
      git push
  fi
fi
popd
popd
