"""
ARISE-I — Plugin Loader
-----------------------
Autonomous File Organization Unit: Classifier Plugin System.
Built by Om // Ironlabs.tech

Implements Roadmap item 3: Plugin Architecture.

Users can drop .py classifier plugins into  ~/.arise-i/plugins/  to extend
or override ARISE-I's default sorting logic without editing the core codebase.

Plugin Contract
---------------
Each plugin is a plain Python file that exposes a single callable:

    def classify(path: pathlib.Path) -> str | None:
        ...

The callable receives the absolute Path to the file being sorted and should
return either:
  - A non-empty string: the *destination category folder name* (e.g. "Projects")
  - None: the plugin abstains; ARISE-I falls through to the next plugin or
    to the default extension-map lookup.

Plugins are evaluated in alphabetical filename order.  The first non-None
return value wins.  If all plugins abstain, the built-in extension-map
is used as the final fallback.

Example plugin  (~/.arise-i/plugins/01_by_date.py)
--------------------------------------------------
    from pathlib import Path
    import datetime

    def classify(path: Path) -> str | None:
        # Sort images taken this year into "Photos-<year>" folders
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".heic"}:
            return None
        year = datetime.datetime.fromtimestamp(path.stat().st_mtime).year
        return f"Photos-{year}"

Installation
------------
    mkdir -p ~/.arise-i/plugins
    cp my_plugin.py ~/.arise-i/plugins/

CLI usage (automatic — plugins load transparently):
    arise-i --path ~/Downloads

Python API:
    from arise_i.core.plugins import load_plugins, classify_with_plugins

    plugins = load_plugins()                         # load from default dir
    category = classify_with_plugins(path, plugins)  # None if all abstain
"""

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Callable

from arise_i.constants import APP_DIR
from arise_i.core.paths import sanitize_folder_name

logger = logging.getLogger("arise_i.plugins")

# Default plugin directory — users drop their .py files here
PLUGIN_DIR: Path = APP_DIR / "plugins"

# Type alias: a callable that accepts a Path and returns str | None
ClassifierPlugin = Callable[[Path], "str | None"]


# ---------------------------------------------------------------------------
# Discovery & loading
# ---------------------------------------------------------------------------

def load_plugins(plugin_dir: Path | None = None) -> list[ClassifierPlugin]:
    """Discover and import all valid classifier plugins from *plugin_dir*.

    Parameters
    ----------
    plugin_dir : Path, optional
        Directory to scan for plugins.  Defaults to ``~/.arise-i/plugins/``.

    Returns
    -------
    list[ClassifierPlugin]
        A list of ``classify(path)`` callables in alphabetical filename order.
        Returns an empty list if the directory doesn't exist or contains no
        valid plugins — ARISE-I operates normally without any plugins.
    """
    if plugin_dir is None:
        plugin_dir = PLUGIN_DIR
        # For the default plugin directory, enforce home directory restriction
        try:
            if not str(plugin_dir.resolve()).startswith(str(Path.home())):
                logger.warning("Default plugin directory outside home directory - rejected: %s", plugin_dir)
                return []
        except Exception:
            logger.warning("Invalid default plugin directory path - rejected")
            return []
    else:
        # Validate custom plugin directory is within safe bounds
        plugin_dir = plugin_dir.resolve()
        try:
            # Custom directories are allowed (user explicitly chose them)
            # but still validate it's an absolute path
            if not plugin_dir.is_absolute():
                logger.warning("Plugin directory must be absolute path - rejected: %s", plugin_dir)
                return []
        except Exception:
            logger.warning("Invalid plugin directory path - rejected")
            return []

    if not plugin_dir.is_dir():
        logger.debug("Plugin directory not found: %s — skipping plugin load.", plugin_dir)
        return []

    plugins: list[ClassifierPlugin] = []

    # Sort for deterministic load order (01_first.py before 02_second.py)
    for py_file in sorted(plugin_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            # Skip __init__.py and private helpers
            continue

        plugin = _load_single_plugin(py_file)
        if plugin is not None:
            plugins.append(plugin)
            logger.info("Plugin loaded: %s", py_file.name)

    if plugins:
        logger.info("%d plugin(s) active.", len(plugins))
    else:
        logger.debug("No plugins found in %s.", plugin_dir)

    return plugins


def _load_single_plugin(py_file: Path) -> "ClassifierPlugin | None":
    """Import one plugin file and return its ``classify`` callable.

    Returns None (and logs a warning) if the file cannot be imported or
    doesn't expose a ``classify`` callable — the error never propagates
    upward so a broken plugin can't crash ARISE-I.
    """
    import uuid
    # Use unique module name to prevent collisions
    module_name = f"_arise_i_plugin_{py_file.stem}_{uuid.uuid4().hex[:8]}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, py_file)
        if spec is None or spec.loader is None:
            logger.warning("Plugin skipped (bad spec): %s", py_file.name)
            return None

        module = importlib.util.module_from_spec(spec)
        # Register in sys.modules so relative imports inside plugins work
        sys.modules[module_name] = module
        spec.loader.exec_module(module)  # type: ignore[attr-defined]

    except Exception as exc:  # noqa: BLE001
        logger.warning("Plugin %s failed to import: %s", py_file.name, exc)
        return None

    classify_fn = getattr(module, "classify", None)
    if not callable(classify_fn):
        logger.warning(
            "Plugin %s has no callable 'classify' — skipped.", py_file.name
        )
        return None

    return classify_fn  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_with_plugins(
    path: Path,
    plugins: list[ClassifierPlugin],
) -> "str | None":
    """Run *path* through each plugin in order; return first non-None result.

    Parameters
    ----------
    path : Path
        The file to classify.
    plugins : list
        Loaded plugin callables (from :func:`load_plugins`).

    Returns
    -------
    str | None
        The category folder name chosen by the first plugin that handles
        the file, or ``None`` if all plugins abstain (caller falls back to
        the built-in extension map).
    """
    for plugin in plugins:
        try:
            result = plugin(path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Plugin raised an exception on %s: %s", path.name, exc)
            result = None

        if isinstance(result, str) and result.strip():
            # Sanitize plugin result to prevent path traversal
            return sanitize_folder_name(result.strip())

    return None
