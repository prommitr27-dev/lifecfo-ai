# Third-party licenses

LifeCFO AI is released under the [MIT License](../../LICENSE). This list
covers every third-party package pinned in the lockfiles: `uv.lock` for the
Python engines, web app, and API, and `mobile/package-lock.json` for the
Expo mobile app. It is generated; do not edit it by hand. Regenerate with:

```bash
uv sync
uv run python scripts/generate_third_party_licenses.py
```

## Result

- Python: 54 packages (46 runtime, 8 development only).
- Mobile (npm): 543 packages (542 app or build tooling, 1 development only).
- **No license conflicts with MIT.** No package is GPL, LGPL, or AGPL only; where a package offers a choice (for example `BSD-3-Clause OR GPL-2.0`), we use the permissive option.

## Notes on licenses with conditions

- **CC-BY-4.0**: Data license (browser support tables). Requires attribution, which this list provides. Used only at build time.
- **MPL-2.0**: File-level copyleft. Using the package unmodified is fine; changes to its own files would have to be shared under MPL-2.0. We do not modify it.
- **Python-2.0** and **PSF-2.0**: permissive Python Software Foundation licenses; keep the copyright notice.
- All other licenses listed (MIT, ISC, BSD, Apache-2.0, 0BSD, Zlib, Unlicense, CC0-1.0, BlueOak-1.0.0, MIT-CMU) are permissive. Apache-2.0 packages ask that their NOTICE file is kept when redistributed.

Platform-specific packages (for example the `lightningcss-*` binaries) are
listed for every platform in the lockfile; only the one for the build
machine is installed.

## Python packages (uv.lock)

| License | Packages |
|---|---|
| MIT | 24 |
| BSD-3-Clause | 15 |
| Apache-2.0 | 8 |
| Apache-2.0 OR BSD-2-Clause | 1 |
| BSD-2-Clause | 1 |
| BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | 1 |
| BSD-3-Clause OR Apache-2.0 | 1 |
| MIT-CMU | 1 |
| MPL-2.0 | 1 |
| PSF-2.0 | 1 |

| Package | Version | License | Scope | MIT compatible |
|---|---|---|---|---|
| altair | 6.3.0 | BSD-3-Clause | runtime | OK |
| annotated-doc | 0.0.5 | MIT | runtime | OK |
| annotated-types | 0.8.0 | MIT | runtime | OK |
| anyio | 4.15.1 | MIT | runtime | OK |
| attrs | 26.1.0 | MIT | runtime | OK |
| certifi | 2026.7.22 | MPL-2.0 | runtime | OK, see note on MPL-2.0 |
| charset-normalizer | 3.5.2 | MIT | runtime | OK |
| click | 8.5.0 | BSD-3-Clause | runtime | OK |
| colorama | 0.4.6 | BSD-3-Clause | dev | OK |
| fastapi | 0.143.5 | MIT | runtime | OK |
| h11 | 0.16.0 | MIT | runtime | OK |
| httpcore | 1.0.9 | BSD-3-Clause | dev | OK |
| httptools | 0.9.0 | MIT | runtime | OK |
| httpx | 0.28.1 | BSD-3-Clause | dev | OK |
| idna | 3.20 | BSD-3-Clause | runtime | OK |
| iniconfig | 2.3.1 | MIT | dev | OK |
| itsdangerous | 2.2.0 | BSD-3-Clause | runtime | OK |
| jinja2 | 3.1.6 | BSD-3-Clause | runtime | OK |
| jsonschema | 4.26.0 | MIT | runtime | OK |
| jsonschema-specifications | 2025.9.1 | MIT | runtime | OK |
| markupsafe | 3.0.4 | BSD-3-Clause | runtime | OK |
| narwhals | 2.27.1 | MIT | runtime | OK |
| numpy | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | runtime | OK |
| opentelemetry-api | 1.45.1 | Apache-2.0 | runtime | OK |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | runtime | OK |
| pandas | 3.0.6 | BSD-3-Clause | runtime | OK |
| pillow | 12.3.0 | MIT-CMU | runtime | OK |
| pluggy | 1.6.0 | MIT | dev | OK |
| protobuf | 7.36.2 | BSD-3-Clause | runtime | OK |
| pyarrow | 25.0.1 | Apache-2.0 | runtime | OK |
| pydantic | 2.14.1 | MIT | runtime | OK |
| pydantic-core | 2.50.1 | MIT | runtime | OK |
| pydeck | 0.9.3 | Apache-2.0 | runtime | OK |
| pygments | 2.21.0 | BSD-2-Clause | dev | OK |
| pytest | 9.1.1 | MIT | dev | OK |
| python-dateutil | 2.9.0.post0 | BSD-3-Clause OR Apache-2.0 | runtime | OK |
| python-multipart | 0.0.32 | Apache-2.0 | runtime | OK |
| pyyaml | 6.0.3 | MIT | runtime | OK |
| referencing | 0.37.0 | MIT | runtime | OK |
| requests | 2.34.2 | Apache-2.0 | runtime | OK |
| rpds-py | 2026.9.1 | MIT | runtime | OK |
| ruff | 0.17.0 | MIT | dev | OK |
| scipy | 1.18.1 | BSD-3-Clause | runtime | OK |
| six | 1.17.0 | MIT | runtime | OK |
| starlette | 1.8.0 | BSD-3-Clause | runtime | OK |
| streamlit | 1.65.0 | Apache-2.0 | runtime | OK |
| toml | 0.10.2 | MIT | runtime | OK |
| typing-extensions | 4.16.0 | PSF-2.0 | runtime | OK |
| typing-inspection | 0.4.4 | MIT | runtime | OK |
| tzdata | 2026.5 | Apache-2.0 | runtime | OK |
| urllib3 | 2.8.0 | MIT | runtime | OK |
| uvicorn | 0.54.0 | BSD-3-Clause | runtime | OK |
| watchdog | 6.0.0 | Apache-2.0 | runtime | OK |
| websockets | 17.2 | BSD-3-Clause | runtime | OK |

## Mobile packages (mobile/package-lock.json)

| License | Packages |
|---|---|
| MIT | 468 |
| ISC | 24 |
| MPL-2.0 | 12 |
| BSD-2-Clause | 10 |
| BSD-3-Clause | 7 |
| Apache-2.0 | 6 |
| BlueOak-1.0.0 | 6 |
| (MIT OR CC0-1.0) | 2 |
| Unlicense | 2 |
| (BSD-3-Clause OR GPL-2.0) | 1 |
| (MIT OR Apache-2.0) | 1 |
| 0BSD | 1 |
| CC-BY-4.0 | 1 |
| CC0-1.0 | 1 |
| Python-2.0 | 1 |

| Package | Version | License | Scope | MIT compatible |
|---|---|---|---|---|
| 2g | 1.0.1 | MIT | app or build | OK |
| @babel/code-frame | 7.29.7 | MIT | app or build | OK |
| @babel/compat-data | 7.29.7 | MIT | app or build | OK |
| @babel/core | 7.29.7 | MIT | app or build | OK |
| @babel/generator | 7.29.8 | MIT | app or build | OK |
| @babel/helper-annotate-as-pure | 7.29.7 | MIT | app or build | OK |
| @babel/helper-compilation-targets | 7.29.7 | MIT | app or build | OK |
| @babel/helper-create-class-features-plugin | 7.29.7 | MIT | app or build | OK |
| @babel/helper-create-regexp-features-plugin | 7.29.10 | MIT | app or build | OK |
| @babel/helper-define-polyfill-provider | 0.6.8 | MIT | app or build | OK |
| @babel/helper-globals | 7.29.7 | MIT | app or build | OK |
| @babel/helper-member-expression-to-functions | 7.29.7 | MIT | app or build | OK |
| @babel/helper-module-imports | 7.29.7 | MIT | app or build | OK |
| @babel/helper-module-transforms | 7.29.7 | MIT | app or build | OK |
| @babel/helper-optimise-call-expression | 7.29.7 | MIT | app or build | OK |
| @babel/helper-plugin-utils | 7.29.7 | MIT | app or build | OK |
| @babel/helper-remap-async-to-generator | 7.29.7 | MIT | app or build | OK |
| @babel/helper-replace-supers | 7.29.7 | MIT | app or build | OK |
| @babel/helper-skip-transparent-expression-wrappers | 7.29.7 | MIT | app or build | OK |
| @babel/helper-string-parser | 7.29.7 | MIT | app or build | OK |
| @babel/helper-validator-identifier | 7.29.7 | MIT | app or build | OK |
| @babel/helper-validator-option | 7.29.7 | MIT | app or build | OK |
| @babel/helper-wrap-function | 7.29.7 | MIT | app or build | OK |
| @babel/helpers | 7.29.10 | MIT | app or build | OK |
| @babel/parser | 7.29.9 | MIT | app or build | OK |
| @babel/plugin-proposal-decorators | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-proposal-export-default-from | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-syntax-decorators | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-syntax-dynamic-import | 7.8.3 | MIT | app or build | OK |
| @babel/plugin-syntax-export-default-from | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-syntax-flow | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-syntax-jsx | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-syntax-nullish-coalescing-operator | 7.8.3 | MIT | app or build | OK |
| @babel/plugin-syntax-optional-chaining | 7.8.3 | MIT | app or build | OK |
| @babel/plugin-syntax-typescript | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-arrow-functions | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-async-generator-functions | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-async-to-generator | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-block-scoping | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-class-properties | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-class-static-block | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-classes | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-destructuring | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-export-namespace-from | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-flow-strip-types | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-for-of | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-logical-assignment-operators | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-modules-commonjs | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-named-capturing-groups-regex | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-nullish-coalescing-operator | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-object-rest-spread | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-optional-catch-binding | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-optional-chaining | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-parameters | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-private-methods | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-private-property-in-object | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-react-display-name | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-react-jsx | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-react-jsx-development | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-react-jsx-self | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-react-jsx-source | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-react-pure-annotations | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-regenerator | 7.29.8 | MIT | app or build | OK |
| @babel/plugin-transform-runtime | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-shorthand-properties | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-template-literals | 7.29.7 | MIT | app or build | OK |
| @babel/plugin-transform-typescript | 7.29.9 | MIT | app or build | OK |
| @babel/plugin-transform-unicode-regex | 7.29.7 | MIT | app or build | OK |
| @babel/preset-typescript | 7.29.7 | MIT | app or build | OK |
| @babel/runtime | 7.29.10 | MIT | app or build | OK |
| @babel/template | 7.29.7 | MIT | app or build | OK |
| @babel/traverse | 7.29.10 | MIT | app or build | OK |
| @babel/types | 7.29.8 | MIT | app or build | OK |
| @expo/cli | 58.1.11 | MIT | app or build | OK |
| @expo/code-signing-certificates | 0.0.7 | MIT | app or build | OK |
| @expo/config | 58.0.6 | MIT | app or build | OK |
| @expo/config-plugins | 58.0.9 | MIT | app or build | OK |
| @expo/config-types | 58.0.3 | MIT | app or build | OK |
| @expo/devcert | 1.2.2 | MIT | app or build | OK |
| @expo/devtools | 58.0.2 | MIT | app or build | OK |
| @expo/dom-webview | 58.0.2 | MIT | app or build | OK |
| @expo/env | 2.5.2 | MIT | app or build | OK |
| @expo/fingerprint | 0.21.5 | MIT | app or build | OK |
| @expo/image-utils | 0.12.5 | MIT | app or build | OK |
| @expo/inline-modules | 0.2.6 | MIT | app or build | OK |
| @expo/json-file | 11.2.1 | MIT | app or build | OK |
| @expo/local-build-cache-provider | 58.0.6 | MIT | app or build | OK |
| @expo/log-box | 58.0.12 | MIT | app or build | OK |
| @expo/log-box-utils | 58.0.2 | MIT | app or build | OK |
| @expo/metro | 58.0.0 | MIT | app or build | OK |
| @expo/metro-config | 58.0.14 | MIT | app or build | OK |
| @expo/metro-file-map | 58.0.5 | MIT | app or build | OK |
| @expo/metro-runtime | 58.0.14 | MIT | app or build | OK |
| @expo/modules-macros-win32-arm64 | 0.20.0 | MIT | app or build | OK |
| @expo/modules-macros-win32-x64 | 0.20.0 | MIT | app or build | OK |
| @expo/osascript | 2.8.1 | MIT | app or build | OK |
| @expo/package-manager | 1.14.2 | MIT | app or build | OK |
| @expo/platforms | 58.0.1 | MIT | app or build | OK |
| @expo/plist | 0.10.1 | MIT | app or build | OK |
| @expo/prebuild-config | 58.0.14 | MIT | app or build | OK |
| @expo/require-utils | 58.0.4 | MIT | app or build | OK |
| @expo/router-server | 58.0.14 | MIT | app or build | OK |
| @expo/schema-utils | 58.0.2 | MIT | app or build | OK |
| @expo/sdk-runtime-versions | 1.0.1 | MIT | app or build | OK |
| @expo/spawn-async | 1.8.0 | MIT | app or build | OK |
| @expo/sudo-prompt | 9.3.2 | MIT | app or build | OK |
| @expo/vector-icons | 15.1.1 | MIT | app or build | OK |
| @expo/ws-tunnel | 2.0.1 | MIT | app or build | OK |
| @expo/xcpretty | 4.4.7 | MIT | app or build | OK |
| @isaacs/ttlcache | 1.4.1 | ISC | app or build | OK |
| @jest/schemas | 29.6.3 | MIT | app or build | OK |
| @jest/types | 29.6.3 | MIT | app or build | OK |
| @jridgewell/gen-mapping | 0.3.13 | MIT | app or build | OK |
| @jridgewell/remapping | 2.3.5 | MIT | app or build | OK |
| @jridgewell/resolve-uri | 3.1.2 | MIT | app or build | OK |
| @jridgewell/source-map | 0.3.11 | MIT | app or build | OK |
| @jridgewell/sourcemap-codec | 1.6.0 | MIT | app or build | OK |
| @jridgewell/trace-mapping | 0.3.31 | MIT | app or build | OK |
| @noxcturnal/noxcturnal-darwin-arm64 | 0.1.5 | MIT | app or build | OK |
| @noxcturnal/noxcturnal-darwin-x64 | 0.1.5 | MIT | app or build | OK |
| @noxcturnal/noxcturnal-linux-arm64-gnu | 0.1.5 | MIT | app or build | OK |
| @noxcturnal/noxcturnal-linux-arm64-musl | 0.1.5 | MIT | app or build | OK |
| @noxcturnal/noxcturnal-linux-x64-gnu | 0.1.5 | MIT | app or build | OK |
| @noxcturnal/noxcturnal-linux-x64-musl | 0.1.5 | MIT | app or build | OK |
| @noxcturnal/noxcturnal-win32-arm64-msvc | 0.1.5 | MIT | app or build | OK |
| @noxcturnal/noxcturnal-win32-x64-msvc | 0.1.5 | MIT | app or build | OK |
| @oxc-project/types | 0.154.0 | MIT | app or build | OK |
| @radix-ui/primitive | 1.2.0 | MIT | app or build | OK |
| @radix-ui/react-collection | 1.2.0 | MIT | app or build | OK |
| @radix-ui/react-compose-refs | 1.1.5 | MIT | app or build | OK |
| @radix-ui/react-context | 1.3.0 | MIT | app or build | OK |
| @radix-ui/react-direction | 1.2.0 | MIT | app or build | OK |
| @radix-ui/react-id | 1.1.4 | MIT | app or build | OK |
| @radix-ui/react-presence | 1.1.11 | MIT | app or build | OK |
| @radix-ui/react-primitive | 2.2.0 | MIT | app or build | OK |
| @radix-ui/react-roving-focus | 1.2.1 | MIT | app or build | OK |
| @radix-ui/react-slot | 1.5.0 | MIT | app or build | OK |
| @radix-ui/react-tabs | 1.2.1 | MIT | app or build | OK |
| @radix-ui/react-use-callback-ref | 1.1.5 | MIT | app or build | OK |
| @radix-ui/react-use-controllable-state | 1.3.0 | MIT | app or build | OK |
| @radix-ui/react-use-effect-event | 0.0.5 | MIT | app or build | OK |
| @radix-ui/react-use-is-hydrated | 0.1.3 | MIT | app or build | OK |
| @radix-ui/react-use-layout-effect | 1.1.4 | MIT | app or build | OK |
| @react-native-async-storage/async-storage | 2.2.0 | MIT | app or build | OK |
| @react-native-masked-view/masked-view | 0.3.2 | MIT | app or build | OK |
| @react-native/asset-utils | 0.88.0 | MIT | app or build | OK |
| @react-native/babel-plugin-codegen | 0.88.0 | MIT | app or build | OK |
| @react-native/babel-preset | 0.88.0 | MIT | app or build | OK |
| @react-native/codegen | 0.88.0 | MIT | app or build | OK |
| @react-native/community-cli-plugin | 0.88.0 | MIT | app or build | OK |
| @react-native/debugger-frontend | 0.88.0 | BSD-3-Clause | app or build | OK |
| @react-native/debugger-shell | 0.88.0 | MIT | app or build | OK |
| @react-native/dev-middleware | 0.88.0 | MIT | app or build | OK |
| @react-native/gradle-plugin | 0.88.0 | MIT | app or build | OK |
| @react-native/js-polyfills | 0.88.0 | MIT | app or build | OK |
| @react-native/metro-babel-transformer | 0.88.0 | MIT | app or build | OK |
| @react-native/metro-config | 0.88.0 | MIT | app or build | OK |
| @react-native/normalize-colors | 0.74.89 | MIT | app or build | OK |
| @react-native/normalize-colors | 0.88.0 | MIT | app or build | OK |
| @react-native/virtualized-lists | 0.88.0 | MIT | app or build | OK |
| @sinclair/typebox | 0.27.12 | MIT | app or build | OK |
| @types/istanbul-lib-coverage | 2.0.6 | MIT | app or build | OK |
| @types/istanbul-lib-report | 3.0.3 | MIT | app or build | OK |
| @types/istanbul-reports | 3.0.4 | MIT | app or build | OK |
| @types/node | 26.6.5 | MIT | app or build | OK |
| @types/react | 19.3.0 | MIT | app or build | OK |
| @types/react-test-renderer | 19.3.0 | MIT | app or build | OK |
| @types/yargs | 17.0.35 | MIT | app or build | OK |
| @types/yargs-parser | 21.0.3 | MIT | app or build | OK |
| @ungap/structured-clone | 1.4.0 | ISC | app or build | OK |
| @xmldom/xmldom | 0.8.15 | MIT | app or build | OK |
| @xmldom/xmldom | 0.9.12 | MIT | app or build | OK |
| accepts | 1.3.8 | MIT | app or build | OK |
| accepts | 2.0.0 | MIT | app or build | OK |
| acorn | 8.19.0 | MIT | app or build | OK |
| agent-base | 7.1.4 | MIT | app or build | OK |
| agent-cli-detector | 0.1.7 | MIT | app or build | OK |
| anser | 1.4.10 | MIT | app or build | OK |
| ansi-escapes | 4.3.2 | MIT | app or build | OK |
| ansi-regex | 4.1.1 | MIT | app or build | OK |
| ansi-regex | 5.0.1 | MIT | app or build | OK |
| ansi-styles | 3.2.1 | MIT | app or build | OK |
| ansi-styles | 4.3.0 | MIT | app or build | OK |
| ansi-styles | 5.2.0 | MIT | app or build | OK |
| arg | 5.0.2 | MIT | app or build | OK |
| argparse | 2.0.1 | Python-2.0 | app or build | OK |
| asap | 2.0.6 | MIT | app or build | OK |
| babel-plugin-polyfill-corejs2 | 0.4.17 | MIT | app or build | OK |
| babel-plugin-polyfill-corejs3 | 0.13.0 | MIT | app or build | OK |
| babel-plugin-polyfill-regenerator | 0.6.8 | MIT | app or build | OK |
| babel-plugin-react-compiler | 1.0.0 | MIT | app or build | OK |
| babel-plugin-react-native-web | 0.21.4 | MIT | app or build | OK |
| babel-plugin-syntax-hermes-parser | 0.36.1 | MIT | app or build | OK |
| babel-plugin-transform-flow-enums | 0.0.2 | MIT | app or build | OK |
| babel-preset-expo | 58.0.17 | MIT | app or build | OK |
| balanced-match | 4.0.4 | MIT | app or build | OK |
| base64-js | 1.5.1 | MIT | app or build | OK |
| baseline-browser-mapping | 2.11.29 | Apache-2.0 | app or build | OK |
| big-integer | 1.6.52 | Unlicense | app or build | OK |
| boolbase | 1.0.0 | ISC | app or build | OK |
| bplist-creator | 0.1.0 | MIT | app or build | OK |
| bplist-parser | 0.3.1 | MIT | app or build | OK |
| brace-expansion | 5.0.12 | MIT | app or build | OK |
| braces | 3.0.3 | MIT | app or build | OK |
| browserslist | 4.29.3 | MIT | app or build | OK |
| bser | 2.1.2 | MIT | app or build | OK |
| buffer-from | 1.1.2 | MIT | app or build | OK |
| bytes | 3.1.2 | MIT | app or build | OK |
| camelcase | 6.3.0 | MIT | app or build | OK |
| caniuse-lite | 1.0.30001816 | CC-BY-4.0 | app or build | OK, see note on CC-BY-4.0 |
| chalk | 2.4.2 | MIT | app or build | OK |
| chalk | 4.1.2 | MIT | app or build | OK |
| ci-info | 3.9.0 | MIT | app or build | OK |
| cli-cursor | 2.1.0 | MIT | app or build | OK |
| cli-spinners | 2.9.2 | MIT | app or build | OK |
| client-only | 0.0.1 | MIT | app or build | OK |
| cliui | 8.0.1 | ISC | app or build | OK |
| clone | 1.0.4 | MIT | app or build | OK |
| color | 4.2.3 | MIT | app or build | OK |
| color-convert | 1.9.3 | MIT | app or build | OK |
| color-convert | 2.0.1 | MIT | app or build | OK |
| color-name | 1.1.3 | MIT | app or build | OK |
| color-name | 1.1.4 | MIT | app or build | OK |
| color-string | 1.9.1 | MIT | app or build | OK |
| commander | 12.1.0 | MIT | app or build | OK |
| commander | 2.20.3 | MIT | app or build | OK |
| commander | 7.2.0 | MIT | app or build | OK |
| compressible | 2.0.18 | MIT | app or build | OK |
| compression | 1.8.2 | MIT | app or build | OK |
| connect | 3.7.0 | MIT | app or build | OK |
| content-type | 2.1.0 | MIT | app or build | OK |
| convert-source-map | 2.0.0 | MIT | app or build | OK |
| core-js-compat | 3.50.0 | MIT | app or build | OK |
| cross-fetch | 3.2.0 | MIT | app or build | OK |
| cross-spawn | 7.0.6 | MIT | app or build | OK |
| css-in-js-utils | 3.1.0 | MIT | app or build | OK |
| css-select | 5.2.2 | BSD-2-Clause | app or build | OK |
| css-tree | 1.1.3 | MIT | app or build | OK |
| css-what | 6.2.2 | BSD-2-Clause | app or build | OK |
| csstype | 3.2.3 | MIT | app or build | OK |
| debug | 2.6.9 | MIT | app or build | OK |
| debug | 3.2.7 | MIT | app or build | OK |
| debug | 4.4.3 | MIT | app or build | OK |
| deepmerge | 4.3.1 | MIT | app or build | OK |
| defaults | 1.0.4 | MIT | app or build | OK |
| define-lazy-prop | 2.0.0 | MIT | app or build | OK |
| depd | 2.0.0 | MIT | app or build | OK |
| destroy | 1.2.0 | MIT | app or build | OK |
| detect-libc | 2.1.2 | Apache-2.0 | app or build | OK |
| dnssd-advertise | 1.1.6 | MIT | app or build | OK |
| dom-serializer | 2.0.0 | MIT | app or build | OK |
| domelementtype | 2.3.0 | BSD-2-Clause | app or build | OK |
| domhandler | 5.0.3 | BSD-2-Clause | app or build | OK |
| domutils | 3.2.2 | BSD-2-Clause | app or build | OK |
| ee-first | 1.1.1 | MIT | app or build | OK |
| electron-to-chromium | 1.5.459 | ISC | app or build | OK |
| emoji-regex | 8.0.0 | MIT | app or build | OK |
| encodeurl | 1.0.2 | MIT | app or build | OK |
| encodeurl | 2.0.0 | MIT | app or build | OK |
| entities | 4.5.0 | BSD-2-Clause | app or build | OK |
| error-stack-parser | 2.1.4 | MIT | app or build | OK |
| es-errors | 1.3.0 | MIT | app or build | OK |
| escalade | 3.2.0 | MIT | app or build | OK |
| escape-html | 1.0.3 | MIT | app or build | OK |
| escape-string-regexp | 1.0.5 | MIT | app or build | OK |
| etag | 1.8.1 | MIT | app or build | OK |
| expo | 58.0.14 | MIT | app or build | OK |
| expo-asset | 58.0.16 | MIT | app or build | OK |
| expo-constants | 58.0.12 | MIT | app or build | OK |
| expo-file-system | 58.0.9 | MIT | app or build | OK |
| expo-font | 58.0.8 | MIT | app or build | OK |
| expo-glass-effect | 58.0.4 | MIT | app or build | OK |
| expo-keep-awake | 58.0.3 | MIT | app or build | OK |
| expo-linking | 58.0.13 | MIT | app or build | OK |
| expo-modules-autolinking | 58.0.13 | MIT | app or build | OK |
| expo-modules-core | 58.0.22 | MIT | app or build | OK |
| expo-modules-jsi | 58.0.15 | MIT | app or build | OK |
| expo-modules-macros | 0.20.0 | MIT | app or build | OK |
| expo-router | 58.0.23 | MIT | app or build | OK |
| expo-server | 58.0.5 | MIT | app or build | OK |
| expo-status-bar | 58.0.3 | MIT | app or build | OK |
| exponential-backoff | 3.1.3 | Apache-2.0 | app or build | OK |
| fb-dotslash | 0.5.8 | (MIT OR Apache-2.0) | app or build | OK |
| fb-watchman | 2.0.4 | MIT | app or build | OK |
| fbjs | 3.0.5 | MIT | app or build | OK |
| fbjs-css-vars | 1.0.2 | MIT | app or build | OK |
| fdir | 6.5.0 | MIT | app or build | OK |
| fetch-nodeshim | 0.4.10 | MIT | app or build | OK |
| fill-range | 7.1.1 | MIT | app or build | OK |
| finalhandler | 1.1.2 | MIT | app or build | OK |
| flow-enums-runtime | 0.0.6 | MIT | app or build | OK |
| flow-estree | 0.327.0 | MIT | app or build | OK |
| flow-estree | 0.331.0 | MIT | app or build | OK |
| flow-parser | 0.327.0 | MIT | app or build | OK |
| flow-parser | 0.331.0 | MIT | app or build | OK |
| fresh | 0.5.2 | MIT | app or build | OK |
| function-bind | 1.1.2 | MIT | app or build | OK |
| gensync | 1.0.0-beta.2 | MIT | app or build | OK |
| get-caller-file | 2.0.5 | ISC | app or build | OK |
| getenv | 2.0.0 | MIT | app or build | OK |
| glob | 13.0.6 | BlueOak-1.0.0 | app or build | OK |
| graceful-fs | 4.2.11 | ISC | app or build | OK |
| has-flag | 3.0.0 | MIT | app or build | OK |
| has-flag | 4.0.0 | MIT | app or build | OK |
| hasown | 2.0.4 | MIT | app or build | OK |
| hermes-compiler | 260318099.0.4 | MIT | app or build | OK |
| hermes-estree | 0.36.1 | MIT | app or build | OK |
| hermes-parser | 0.36.1 | MIT | app or build | OK |
| hosted-git-info | 7.0.2 | ISC | app or build | OK |
| http-errors | 2.0.1 | MIT | app or build | OK |
| https-proxy-agent | 7.0.6 | MIT | app or build | OK |
| hyphenate-style-name | 1.1.0 | BSD-3-Clause | app or build | OK |
| ignore | 5.3.2 | MIT | app or build | OK |
| inherits | 2.0.4 | ISC | app or build | OK |
| inline-style-prefixer | 7.0.1 | MIT | app or build | OK |
| invariant | 2.2.4 | MIT | app or build | OK |
| is-arrayish | 0.3.4 | MIT | app or build | OK |
| is-core-module | 2.17.0 | MIT | app or build | OK |
| is-docker | 2.2.1 | MIT | app or build | OK |
| is-fullwidth-code-point | 3.0.0 | MIT | app or build | OK |
| is-number | 7.0.0 | MIT | app or build | OK |
| is-plain-obj | 2.1.0 | MIT | app or build | OK |
| is-wsl | 2.2.0 | MIT | app or build | OK |
| isexe | 2.0.0 | ISC | app or build | OK |
| jest-get-type | 29.6.3 | MIT | app or build | OK |
| jest-util | 29.7.0 | MIT | app or build | OK |
| jest-validate | 29.7.0 | MIT | app or build | OK |
| jest-worker | 29.7.0 | MIT | app or build | OK |
| jimp-compact | 0.16.1 | MIT | app or build | OK |
| js-tokens | 4.0.0 | MIT | app or build | OK |
| js-yaml | 4.3.2 | MIT | app or build | OK |
| jsc-safe-url | 0.2.4 | 0BSD | app or build | OK |
| jsesc | 3.1.0 | MIT | app or build | OK |
| json5 | 2.2.3 | MIT | app or build | OK |
| kleur | 3.0.3 | MIT | app or build | OK |
| lan-network | 0.2.1 | MIT | app or build | OK |
| leven | 3.1.0 | MIT | app or build | OK |
| lightningcss | 1.33.0 | MPL-2.0 | app or build | OK, see note on MPL-2.0 |
| lightningcss-android-arm64 | 1.33.0 | MPL-2.0 | app or build | OK, see note on MPL-2.0 |
| lightningcss-darwin-arm64 | 1.33.0 | MPL-2.0 | app or build | OK, see note on MPL-2.0 |
| lightningcss-darwin-x64 | 1.33.0 | MPL-2.0 | app or build | OK, see note on MPL-2.0 |
| lightningcss-freebsd-x64 | 1.33.0 | MPL-2.0 | app or build | OK, see note on MPL-2.0 |
| lightningcss-linux-arm-gnueabihf | 1.33.0 | MPL-2.0 | app or build | OK, see note on MPL-2.0 |
| lightningcss-linux-arm64-gnu | 1.33.0 | MPL-2.0 | app or build | OK, see note on MPL-2.0 |
| lightningcss-linux-arm64-musl | 1.33.0 | MPL-2.0 | app or build | OK, see note on MPL-2.0 |
| lightningcss-linux-x64-gnu | 1.33.0 | MPL-2.0 | app or build | OK, see note on MPL-2.0 |
| lightningcss-linux-x64-musl | 1.33.0 | MPL-2.0 | app or build | OK, see note on MPL-2.0 |
| lightningcss-win32-arm64-msvc | 1.33.0 | MPL-2.0 | app or build | OK, see note on MPL-2.0 |
| lightningcss-win32-x64-msvc | 1.33.0 | MPL-2.0 | app or build | OK, see note on MPL-2.0 |
| lodash.debounce | 4.0.8 | MIT | app or build | OK |
| lodash.throttle | 4.1.1 | MIT | app or build | OK |
| log-symbols | 2.2.0 | MIT | app or build | OK |
| loose-envify | 1.4.0 | MIT | app or build | OK |
| lru-cache | 10.4.3 | ISC | app or build | OK |
| lru-cache | 11.5.3 | BlueOak-1.0.0 | app or build | OK |
| lru-cache | 5.1.1 | ISC | app or build | OK |
| makeerror | 1.0.12 | BSD-3-Clause | app or build | OK |
| mdn-data | 2.0.14 | CC0-1.0 | app or build | OK |
| memoize-one | 5.2.1 | MIT | app or build | OK |
| memoize-one | 6.0.0 | MIT | app or build | OK |
| merge-options | 3.0.4 | MIT | app or build | OK |
| merge-stream | 2.0.0 | MIT | app or build | OK |
| metro | 0.87.1 | MIT | app or build | OK |
| metro-babel-transformer | 0.87.1 | MIT | app or build | OK |
| metro-cache | 0.87.1 | MIT | app or build | OK |
| metro-cache-key | 0.87.1 | MIT | app or build | OK |
| metro-config | 0.87.1 | MIT | app or build | OK |
| metro-core | 0.87.1 | MIT | app or build | OK |
| metro-file-map | 0.87.1 | MIT | app or build | OK |
| metro-minify-terser | 0.87.1 | MIT | app or build | OK |
| metro-resolver | 0.87.1 | MIT | app or build | OK |
| metro-runtime | 0.87.1 | MIT | app or build | OK |
| metro-source-map | 0.87.1 | MIT | app or build | OK |
| metro-symbolicate | 0.87.1 | MIT | app or build | OK |
| metro-transform-plugins | 0.87.1 | MIT | app or build | OK |
| metro-transform-worker | 0.87.1 | MIT | app or build | OK |
| micromatch | 4.0.8 | MIT | app or build | OK |
| mime | 1.6.0 | MIT | app or build | OK |
| mime-db | 1.52.0 | MIT | app or build | OK |
| mime-db | 1.54.0 | MIT | app or build | OK |
| mime-types | 2.1.35 | MIT | app or build | OK |
| mime-types | 3.0.2 | MIT | app or build | OK |
| mimic-fn | 1.2.0 | MIT | app or build | OK |
| minimatch | 10.2.6 | BlueOak-1.0.0 | app or build | OK |
| minipass | 7.1.3 | BlueOak-1.0.0 | app or build | OK |
| ms | 2.0.0 | MIT | app or build | OK |
| ms | 2.1.3 | MIT | app or build | OK |
| multitars | 1.0.2 | MIT | app or build | OK |
| nanoid | 3.3.20 | MIT | app or build | OK |
| negotiator | 0.6.3 | MIT | app or build | OK |
| negotiator | 0.6.4 | MIT | app or build | OK |
| negotiator | 1.1.0 | MIT | app or build | OK |
| node-fetch | 2.7.0 | MIT | app or build | OK |
| node-forge | 1.4.0 | (BSD-3-Clause OR GPL-2.0) | app or build | OK (we use it under BSD-3-Clause) |
| node-int64 | 0.4.0 | MIT | app or build | OK |
| node-releases | 2.0.59 | MIT | app or build | OK |
| noxcturnal | 0.1.5 | MIT | app or build | OK |
| npm-package-arg | 11.0.3 | ISC | app or build | OK |
| nth-check | 2.1.1 | BSD-2-Clause | app or build | OK |
| nullthrows | 1.1.1 | MIT | app or build | OK |
| ob1 | 0.87.1 | MIT | app or build | OK |
| object-assign | 4.1.1 | MIT | app or build | OK |
| on-finished | 2.3.0 | MIT | app or build | OK |
| on-finished | 2.4.1 | MIT | app or build | OK |
| on-headers | 1.1.0 | MIT | app or build | OK |
| onetime | 2.0.1 | MIT | app or build | OK |
| open | 8.4.2 | MIT | app or build | OK |
| ora | 3.4.0 | MIT | app or build | OK |
| parse-png | 2.1.0 | MIT | app or build | OK |
| parseurl | 1.3.3 | MIT | app or build | OK |
| path-key | 3.1.1 | MIT | app or build | OK |
| path-parse | 1.0.7 | MIT | app or build | OK |
| path-scurry | 2.0.2 | BlueOak-1.0.0 | app or build | OK |
| picocolors | 1.1.1 | ISC | app or build | OK |
| picomatch | 2.3.2 | MIT | app or build | OK |
| picomatch | 4.0.7 | MIT | app or build | OK |
| plist | 3.1.1 | MIT | app or build | OK |
| pngjs | 3.4.0 | MIT | app or build | OK |
| postcss | 8.5.30 | MIT | app or build | OK |
| postcss-value-parser | 4.2.0 | MIT | app or build | OK |
| pretty-format | 29.7.0 | MIT | app or build | OK |
| proc-log | 4.2.0 | ISC | app or build | OK |
| progress | 2.0.3 | MIT | app or build | OK |
| promise | 7.3.1 | MIT | app or build | OK |
| promise | 8.3.0 | MIT | app or build | OK |
| prompts | 2.4.2 | MIT | app or build | OK |
| range-parser | 1.2.1 | MIT | app or build | OK |
| react | 19.3.0 | MIT | app or build | OK |
| react-devtools-core | 6.1.5 | MIT | app or build | OK |
| react-dom | 19.3.0 | MIT | app or build | OK |
| react-fast-compare | 3.2.2 | MIT | app or build | OK |
| react-freeze | 1.0.4 | MIT | app or build | OK |
| react-is | 18.3.1 | MIT | app or build | OK |
| react-is | 19.3.1 | MIT | app or build | OK |
| react-native | 0.88.0 | MIT | app or build | OK |
| react-native-drawer-layout | 4.2.12 | MIT | app or build | OK |
| react-native-gesture-handler | 3.4.0 | MIT | app or build | OK |
| react-native-is-edge-to-edge | 1.3.1 | MIT | app or build | OK |
| react-native-reanimated | 4.7.1 | MIT | app or build | OK |
| react-native-safe-area-context | 5.10.1 | MIT | app or build | OK |
| react-native-screens | 4.30.0 | MIT | app or build | OK |
| react-native-svg | 15.16.0 | MIT | app or build | OK |
| react-native-web | 0.21.4 | MIT | app or build | OK |
| react-native-worklets | 0.13.0 | MIT | app or build | OK |
| react-refresh | 0.14.2 | MIT | app or build | OK |
| regenerate | 1.5.0 | MIT | app or build | OK |
| regenerate-unicode-properties | 10.3.0 | MIT | app or build | OK |
| regenerator-runtime | 0.13.11 | MIT | app or build | OK |
| regexpu-core | 6.5.3 | MIT | app or build | OK |
| regjsgen | 0.8.0 | MIT | app or build | OK |
| regjsparser | 0.13.4 | BSD-2-Clause | app or build | OK |
| require-directory | 2.1.1 | MIT | app or build | OK |
| resolve | 1.22.13 | MIT | app or build | OK |
| resolve-from | 5.0.0 | MIT | app or build | OK |
| resolve-workspace-root | 2.0.1 | MIT | app or build | OK |
| restore-cursor | 2.0.0 | MIT | app or build | OK |
| safe-buffer | 5.2.1 | MIT | app or build | OK |
| sandbox-cli-detector | 0.2.0 | MIT | app or build | OK |
| sax | 1.6.1 | BlueOak-1.0.0 | app or build | OK |
| scheduler | 0.28.0 | MIT | app or build | OK |
| semver | 6.3.1 | ISC | app or build | OK |
| semver | 7.8.5 | ISC | app or build | OK |
| send | 0.19.2 | MIT | app or build | OK |
| serialize-error | 2.1.0 | MIT | app or build | OK |
| serve-static | 1.16.3 | MIT | app or build | OK |
| server-only | 0.0.1 | MIT | app or build | OK |
| setimmediate | 1.0.5 | MIT | app or build | OK |
| setprototypeof | 1.2.0 | ISC | app or build | OK |
| sf-symbols-typescript | 2.2.0 | MIT | app or build | OK |
| shebang-command | 2.0.0 | MIT | app or build | OK |
| shebang-regex | 3.0.0 | MIT | app or build | OK |
| shell-quote | 1.12.0 | MIT | app or build | OK |
| signal-exit | 3.0.7 | ISC | app or build | OK |
| simple-plist | 1.3.1 | MIT | app or build | OK |
| simple-swizzle | 0.2.4 | MIT | app or build | OK |
| sisteransi | 1.0.5 | MIT | app or build | OK |
| slugify | 1.6.9 | MIT | app or build | OK |
| source-map | 0.5.7 | BSD-3-Clause | app or build | OK |
| source-map | 0.6.1 | BSD-3-Clause | app or build | OK |
| source-map-js | 1.2.2 | BSD-3-Clause | app or build | OK |
| source-map-support | 0.5.21 | MIT | app or build | OK |
| stackframe | 1.3.4 | MIT | app or build | OK |
| stacktrace-parser | 0.1.11 | MIT | app or build | OK |
| standard-navigation | 0.0.5 | MIT | app or build | OK |
| statuses | 1.5.0 | MIT | app or build | OK |
| statuses | 2.0.2 | MIT | app or build | OK |
| stream-buffers | 2.2.0 | Unlicense | app or build | OK |
| string-width | 4.2.3 | MIT | app or build | OK |
| strip-ansi | 5.2.0 | MIT | app or build | OK |
| strip-ansi | 6.0.1 | MIT | app or build | OK |
| structured-headers | 0.4.1 | MIT | app or build | OK |
| styleq | 0.1.3 | MIT | app or build | OK |
| supports-color | 5.5.0 | MIT | app or build | OK |
| supports-color | 7.2.0 | MIT | app or build | OK |
| supports-color | 8.1.1 | MIT | app or build | OK |
| supports-hyperlinks | 2.3.0 | MIT | app or build | OK |
| supports-preserve-symlinks-flag | 1.0.0 | MIT | app or build | OK |
| terminal-link | 2.1.1 | MIT | app or build | OK |
| terser | 5.51.2 | BSD-2-Clause | app or build | OK |
| throat | 5.0.0 | MIT | app or build | OK |
| tinyglobby | 0.2.17 | MIT | app or build | OK |
| tmpl | 1.0.5 | BSD-3-Clause | app or build | OK |
| to-regex-range | 5.0.1 | MIT | app or build | OK |
| toidentifier | 1.0.1 | MIT | app or build | OK |
| toqr | 0.1.1 | MIT | app or build | OK |
| tr46 | 0.0.3 | MIT | app or build | OK |
| type-fest | 0.21.3 | (MIT OR CC0-1.0) | app or build | OK |
| type-fest | 0.7.1 | (MIT OR CC0-1.0) | app or build | OK |
| typescript | 6.0.3 | Apache-2.0 | dev | OK |
| ua-parser-js | 1.0.41 | MIT | app or build | OK |
| undici-types | 8.9.0 | MIT | app or build | OK |
| unicode-canonical-property-names-ecmascript | 2.0.1 | MIT | app or build | OK |
| unicode-match-property-ecmascript | 2.0.0 | MIT | app or build | OK |
| unicode-match-property-value-ecmascript | 2.2.1 | MIT | app or build | OK |
| unicode-property-aliases-ecmascript | 2.2.0 | MIT | app or build | OK |
| unpipe | 1.0.0 | MIT | app or build | OK |
| update-browserslist-db | 1.3.4 | MIT | app or build | OK |
| use-latest-callback | 0.2.6 | MIT | app or build | OK |
| utils-merge | 1.0.1 | MIT | app or build | OK |
| uuid | 7.0.3 | MIT | app or build | OK |
| validate-npm-package-name | 5.0.1 | ISC | app or build | OK |
| vary | 1.1.2 | MIT | app or build | OK |
| vlq | 1.0.1 | MIT | app or build | OK |
| walker | 1.0.8 | Apache-2.0 | app or build | OK |
| warn-once | 0.1.1 | MIT | app or build | OK |
| wcwidth | 1.0.1 | MIT | app or build | OK |
| webidl-conversions | 3.0.1 | BSD-2-Clause | app or build | OK |
| whatwg-fetch | 3.6.20 | MIT | app or build | OK |
| whatwg-url | 5.0.0 | MIT | app or build | OK |
| whatwg-url-minimum | 0.2.0 | MIT | app or build | OK |
| which | 2.0.2 | ISC | app or build | OK |
| wrap-ansi | 7.0.0 | MIT | app or build | OK |
| ws | 7.5.13 | MIT | app or build | OK |
| ws | 8.22.0 | MIT | app or build | OK |
| xcode | 3.0.1 | Apache-2.0 | app or build | OK |
| xml2js | 0.6.0 | MIT | app or build | OK |
| xmlbuilder | 11.0.1 | MIT | app or build | OK |
| xmlbuilder | 15.1.1 | MIT | app or build | OK |
| y18n | 5.0.8 | ISC | app or build | OK |
| yallist | 3.1.1 | ISC | app or build | OK |
| yargs | 17.7.3 | MIT | app or build | OK |
| yargs-parser | 21.1.1 | ISC | app or build | OK |
| zod | 3.25.76 | MIT | app or build | OK |
