# CLAUDE.md

Guidance for AI assistants working in this repository.

## What this repository is

`SmartThingsPublic` is the official SmartThings catalog of **SmartApps** and
**Device Type Handlers (DTHs)** — the legacy (Groovy, "Classic") SmartThings
platform. Every file is Groovy source that runs *server-side in the SmartThings
cloud sandbox*, not on a JVM you control. There is no application to run, no
service to start, and no test suite. The repository is a source catalog that
gets compiled for validation and then deployed to S3 by CI.

Two source roots, ~470 Groovy files total:

| Path           | Contents                              | Count  |
| -------------- | ------------------------------------- | ------ |
| `smartapps/`   | SmartApps (automations, integrations) | ~187   |
| `devicetypes/` | Device Type Handlers                  | ~279   |

## Directory layout and naming — this is load-bearing

The layout is dictated by the SmartThings IDE's GitHub integration. It is not a
stylistic choice; the platform resolves files by path.

```
<smartapps|devicetypes>/<namespace>/<hyphenated-name>.src/<hyphenated-name>.groovy
```

Rules that hold across the entire repo (verified — zero exceptions):

1. `<namespace>` is the value of the `namespace:` field inside the file, with
   `.` and other punctuation replaced by `-`
   (`com.obycode` → `com-obycode`, `smartthings` → `smartthings`).
2. The directory ends in `.src`.
3. The `.groovy` file basename is **identical** to the `.src` directory name.
4. Exactly one `.groovy` file per `.src` directory. Never add a second.
5. The `.src` directory name is the `name:` field lowercased and hyphenated
   ("Big Turn ON" → `big-turn-on.src`).

An optional `i18n/` subdirectory may sit alongside the `.groovy` file
(22 exist) holding `<locale>.properties` files (`en-US.properties`,
`de-DE.properties`, …) in the format:

```
'''Source string in the app'''=Localized string
```

Notable namespaces:

- `smartapps/smartthings/` — 106 first-party SmartApps.
- `devicetypes/smartthings/` — 188 first-party DTHs; the bulk of active work.
- `devicetypes/smartthings/testing/` — 23 `simulated-*` DTHs used for virtual
  devices in testing. Add a simulated handler here when a new capability needs
  one.
- `devicetypes/capabilities/` — 16 `*-capability.src` reference handlers, one
  per core capability.
- Everything else (`dianoga`, `erocm123`, `rachio`, `fibargroup`, …) is
  community- or partner-contributed. **Do not refactor another namespace's code
  unless the task explicitly asks for it** — those files are owned by their
  contributors.

## Build, check, and CI

Gradle 2.10 via the wrapper. `build.gradle` defines two Groovy source sets
(`devicetypes` and `smartapps`) so the catalog can be *compiled* against stubbed
platform libraries — that is the only automated verification that exists.

```bash
./gradlew check
./gradlew compileSmartappsGroovy compileDevicetypesGroovy
```

**These commands cannot run in a sandbox without credentials.** Dependencies
(`smartthings:appengine-common`, `appengine-z-wave`, `appengine-zigbee`) live in
a private Artifactory repo and require:

```bash
./gradlew compileSmartappsGroovy \
  -PsmartThingsArtifactoryUserName="$ARTIFACTORY_USERNAME" \
  -PsmartThingsArtifactoryPassword="$ARTIFACTORY_PASSWORD"
```

If you have no credentials, say so rather than reporting a build failure as a
code problem. Verify changes by reading and by pattern-matching against
neighboring handlers instead.

CircleCI (`.circleci/config.yml`) runs `check` + both compile tasks on every
branch, then:

- `master` → `deploy-dev` (uploads archives to the Dev S3 buckets)
- `staging` → `deploy-stage`
- `production` → prod (deployed outside this config)

Upstream promotion flows `master` → `staging` → `production` via merge PRs;
the git history is full of `Merge pull request … from SmartThingsCommunity/staging`.

There is **no linter config, no CodeNarc, no unit tests, and no `src/test`** in
this repository. Do not invent a test harness; do not claim tests pass.

## SmartApp anatomy

```groovy
/**
 *  Copyright 2015 SmartThings
 *  ... Apache 2.0 header ...
 */
definition(
    name: "Big Turn ON",
    namespace: "smartthings",
    author: "SmartThings",
    description: "...",
    category: "Convenience",
    iconUrl: "https://s3.amazonaws.com/smartapp-icons/Meta/light_outlet.png",
    iconX2Url: "...@2x.png"
)

preferences {
    section("When I touch the app, turn on...") {
        input "switches", "capability.switch", multiple: true
    }
}

def installed() { subscribe(app, appTouch) }
def updated()   { unsubscribe(); subscribe(app, appTouch) }
def appTouch(evt) { switches?.on() }
```

Invariants worth preserving:

- `installed()` and `updated()` are the lifecycle entry points; `updated()`
  virtually always calls `unsubscribe()` (and `unschedule()` when timers are
  used) before re-registering. Forgetting this causes duplicate subscriptions.
- Inputs are declared by *capability* (`capability.switch`,
  `capability.temperatureMeasurement`), which is how devices are matched.
- Scheduling: `runIn`, `runEvery5Minutes`, `schedule`, `runOnce`. State persists
  across executions only via the `state` map (and `atomicState` for
  concurrency-sensitive values).
- ~30 SmartApps expose a web/OAuth surface via a `mappings { path(...) }` block.
- ~25 create child devices with `addChildDevice(...)`; those pair with a DTH
  elsewhere in the repo — change both together.

## Device Type Handler anatomy

```groovy
metadata {
    definition (name: "ZigBee Switch", namespace: "smartthings", author: "SmartThings",
                ocfDeviceType: "oic.d.switch", runLocally: true,
                minHubCoreVersion: '000.019.00012', executeCommandsLocally: true) {
        capability "Actuator"
        capability "Switch"
        capability "Health Check"

        fingerprint profileId: "0104", inClusters: "0000, 0003, 0006",
                    manufacturer: "Leviton", model: "ZSS-10",
                    deviceJoinName: "Leviton Switch"
    }
    simulator { /* status / reply pairs */ }
    tiles(scale: 2) { multiAttributeTile(...) ; main "switch" ; details([...]) }
}

def parse(String description) { ... }   // required — inbound protocol messages
def on()  { zigbee.on() }               // one method per capability command
def ping(){ refresh() }                 // used by Device-Watch
```

Key points:

- `parse()` is mandatory. ZigBee handlers use `zigbee.getEvent(description)` /
  `zigbee.parseDescriptionAsMap()`; Z-Wave handlers use
  `zwave.parse(description, [0x80: 1, 0x84: 1, ...])` with an explicit command
  class version map, then dispatch through `zwaveEvent(...)` overloads.
- **Fingerprints are the single most common change in this repo.** Most commits
  add one `fingerprint` line to an existing DTH so a new device joins with the
  right handler. Add fingerprints to the *existing* handler for that device
  class rather than creating a near-duplicate DTH. Always include
  `deviceJoinName`. ZigBee fingerprints key off
  `profileId`/`inClusters`/`outClusters`/`manufacturer`/`model`; Z-Wave off
  `mfr`/`prod`/`model`.
- Health Check: 158 handlers declare `capability "Health Check"`; 42 set the
  `DeviceWatch-Enroll` / `DeviceWatch-DeviceStatus` data. When a handler has it,
  `installed()`/`updated()` must send the `checkInterval` event, and `ping()`
  must actually reach the device.
- `tiles` drive the Classic app UI. `main` sets the icon in device lists;
  `details` sets the ordering on the detail screen.

## Code conventions

- **Apache 2.0 header on every file.** All 404 non-trivial handlers carry it.
  Copy the header from a neighboring file in the same namespace when creating
  one.
- **Indentation is inconsistent by design of history**: ~404 files use tabs,
  ~264 use 4 spaces. Match the file you are editing; never reindent a whole
  file, since that destroys the blame that maintainers rely on.
- Groovy idioms used throughout: safe navigation (`switches?.on()`), GString
  interpolation in `log.debug "…$evt"`, implicit returns, and map-literal
  arguments without parentheses.
- Logging is `log.debug` / `log.warn` / `log.error` on the injected `log`
  object. Keep logging in place; it is the only debugging channel on device.
- The runtime injects `zigbee`, `zwave`, `device`, `location`, `settings`,
  `state`, `app`, and `log`. Do not `import` platform classes; 156 files
  reference `physicalgraph.*` types only in signatures where the sandbox
  requires it.
- Never add third-party imports, file/network I/O outside the sandbox HTTP
  helpers (`httpGet`, `httpPost`, `asynchttp_v1`), or `@Grab`. The sandbox
  rejects them.

## Making changes

1. Identify whether the change belongs in an existing handler. For new device
   support, a fingerprint added to a generic handler (`ZigBee Switch`,
   `Z-Wave Switch`, `ZigBee Contact Sensor`, …) is almost always correct.
2. If a new handler really is needed, create the full
   `namespace/name.src/name.groovy` triple and copy the closest existing
   handler as the starting point.
3. Keep the diff minimal and local to the file(s) involved. Cross-cutting
   refactors across namespaces are out of scope for nearly every task here.
4. Commit messages follow the upstream ticket convention seen in history:
   `ICP-6819 <summary>`, `[WWST-1632] <summary>`, or a plain descriptive line
   (`Add fingerprint for BeSense door window sensor`).

## Reference links

- Platform docs: http://docs.smartthings.com
- GitHub integration (explains the `.src` layout):
  http://docs.smartthings.com/en/latest/tools-and-ide/github-integration.html
- IDE & simulator: http://ide.smartthings.com
- Community forums: http://community.smartthings.com
