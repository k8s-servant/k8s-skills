# Changelog

## [0.3.1](https://github.com/k8s-servant/k8s-skills/compare/v0.3.0...v0.3.1) (2026-10-24)


### Documentation

* lead the install guide with the skills CLI and a plain copy ([#38](https://github.com/k8s-servant/k8s-skills/issues/38)) ([c52e64d](https://github.com/k8s-servant/k8s-skills/commit/c52e64d8242e568f2217ed3ba7fdb8d8be0b8956))
* make copying to the home directory the main manual install ([#40](https://github.com/k8s-servant/k8s-skills/issues/40)) ([0993d02](https://github.com/k8s-servant/k8s-skills/commit/0993d0238940a851ba66dcb166b99fee64129449))

## [0.3.0](https://github.com/k8s-servant/k8s-skills/compare/v0.2.0...v0.3.0) (2026-10-24)


### Features

* **skills:** add k8s-network-troubleshooting ([#36](https://github.com/k8s-servant/k8s-skills/issues/36)) ([a308a4e](https://github.com/k8s-servant/k8s-skills/commit/a308a4e7d41de06ba83841074e9c71cfb061e9d6))
* **skills:** add k8s-node-troubleshooting ([#33](https://github.com/k8s-servant/k8s-skills/issues/33)) ([e4fd766](https://github.com/k8s-servant/k8s-skills/commit/e4fd766baf103f2aa15401514783ce4944506e45))
* **skills:** add k8s-storage-troubleshooting ([#37](https://github.com/k8s-servant/k8s-skills/issues/37)) ([ade187f](https://github.com/k8s-servant/k8s-skills/commit/ade187f5aaffa17ed23a28fc194f63142125adea))

## [0.2.0](https://github.com/k8s-servant/k8s-skills/compare/v0.1.1...v0.2.0) (2026-10-24)


### ⚠ BREAKING CHANGES

* read first, ask before changing ([#26](https://github.com/k8s-servant/k8s-skills/issues/26))

### Features

* read first, ask before changing ([#26](https://github.com/k8s-servant/k8s-skills/issues/26)) ([7d7fc79](https://github.com/k8s-servant/k8s-skills/commit/7d7fc79c640de8d387a29f0d59212e633a746277))
* **skills:** add k8s-triage ([#30](https://github.com/k8s-servant/k8s-skills/issues/30)) ([4db5b4f](https://github.com/k8s-servant/k8s-skills/commit/4db5b4fa0c87f808de5e571f0e2efd1879068005))
* **skills:** ask before running k8s-workload-troubleshooting fixes ([#32](https://github.com/k8s-servant/k8s-skills/issues/32)) ([55dfb7a](https://github.com/k8s-servant/k8s-skills/commit/55dfb7a53daa0ce3ce99ce37d1d6c9f36060bb55))

## [0.1.1](https://github.com/k8s-servant/k8s-skills/compare/v0.1.0...v0.1.1) (2026-10-23)


### Documentation

* mark the install paths verified against v0.1.0 ([#20](https://github.com/k8s-servant/k8s-skills/issues/20)) ([85f7678](https://github.com/k8s-servant/k8s-skills/commit/85f7678f598e29cdeff709bb144f89852673268c))

## 0.1.0 (2026-10-23)


### Features

* **check:** check skill structure and scenarios ([8be464d](https://github.com/k8s-servant/k8s-skills/commit/8be464d367958954962e1d9f71a795ec0f807487))
* **check:** enforce the read-only command allow-list ([5e9b627](https://github.com/k8s-servant/k8s-skills/commit/5e9b627aa613eb2b368d145a9e8418f6bf6b2ea9))
* **check:** validate skill frontmatter ([7c860b8](https://github.com/k8s-servant/k8s-skills/commit/7c860b873d7bb02822974acec568ba0102e6fb2e))
* generate install manifests for Claude Code and Gemini CLI ([590ea82](https://github.com/k8s-servant/k8s-skills/commit/590ea820ee95a932ab944e8a72250e78e04f2726))
* **skills:** add k8s-workload-troubleshooting ([3af884d](https://github.com/k8s-servant/k8s-skills/commit/3af884d20bd5a0eec75c52e257ad615668cfa240))


### Bug fixes

* add a marketplace description ([e97ff8f](https://github.com/k8s-servant/k8s-skills/commit/e97ff8f7506ca50753423da88af879fb118b1256))
* **check:** close allow-list bypasses found in review ([275bedf](https://github.com/k8s-servant/k8s-skills/commit/275bedfbc0374a3f85f87bcf293e9731aee843d6))
* **check:** close fence, continuation and fix-block bypasses ([a4a06f7](https://github.com/k8s-servant/k8s-skills/commit/a4a06f7a03a0a32db8ff98a4aa83c6e5df6ff8ba))
* **check:** link-check nested references ([05886b2](https://github.com/k8s-servant/k8s-skills/commit/05886b2b4a031ac5ec428a4bbd4c903cbee7990e))
* **check:** reject blocking and file-reading kubectl flags ([a3049df](https://github.com/k8s-servant/k8s-skills/commit/a3049dfb09ba1fca28c42aa125c4c897e79ec9c4))
* **check:** report hidden skill folders and test folders without a skill ([3b0f755](https://github.com/k8s-servant/k8s-skills/commit/3b0f755da1659c8d45d5a12e08ba5f285a43f2b1))
* **check:** stop flagging prose mentions of kubectl ([ecf5bf3](https://github.com/k8s-servant/k8s-skills/commit/ecf5bf3fdc0f3efbaead1bf11f10dfc0e492b87e))
* **ci:** install dependencies before packaging release zips ([a5aedd6](https://github.com/k8s-servant/k8s-skills/commit/a5aedd67e8e7813641d79e4acbb43f79bc56e414))
* **package:** leave dotfiles and __pycache__ out of release zips ([635badc](https://github.com/k8s-servant/k8s-skills/commit/635badc0f995b7e06061a922d24b00df1beb3915))
* report broken skills instead of crashing in manifests ([a294ac8](https://github.com/k8s-servant/k8s-skills/commit/a294ac81655782b024fe9bf8e423c779dd38a3da))
* **skills:** read the real progress deadline and tidy workload scenarios ([1681ffe](https://github.com/k8s-servant/k8s-skills/commit/1681ffeedf97cf282faa2d402c7853e40908a781))


### Documentation

* add README, contributing guide and agent guidance ([5a5bb12](https://github.com/k8s-servant/k8s-skills/commit/5a5bb12b1afd0383a9a249295743d64bf6986b59))
* bring the design in line with what shipped ([c102e2a](https://github.com/k8s-servant/k8s-skills/commit/c102e2afc9443291a81b633918f299a605abfde7))
* **ci:** drop the promise of on-demand reviews for fork PRs ([b31b3e9](https://github.com/k8s-servant/k8s-skills/commit/b31b3e9042dfd4d22b69d6ba109863419c872986))
* flag unverified install paths, explain ca.crt and rename the templates ([8431aee](https://github.com/k8s-servant/k8s-skills/commit/8431aeea70795ce8196fd69a8cca82bf21f62d65))
* leave agent permissions to the user and point to RBAC ([b9d95e7](https://github.com/k8s-servant/k8s-skills/commit/b9d95e7b33611fd714514df991131ae54dcb643c))
