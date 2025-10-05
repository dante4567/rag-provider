"""
Obsidian Vault Configurator
Creates pre-configured .obsidian folder for consistent experience across clients
"""

import json
from pathlib import Path
import shutil
import logging

logger = logging.getLogger(__name__)


class ObsidianConfigurator:
    """Configures Obsidian vault with standard settings"""

    def __init__(self, vault_path: Path):
        self.vault_path = Path(vault_path)
        self.obsidian_dir = self.vault_path / ".obsidian"

    def setup_complete_config(self):
        """Create complete .obsidian configuration"""

        self.obsidian_dir.mkdir(exist_ok=True)

        # Core configuration files
        self.create_app_config()
        self.create_appearance_config()
        self.create_core_plugins_config()
        self.create_community_plugins_config()

        # Plugin configurations
        self.create_dataview_config()
        self.create_templater_config()
        self.create_graph_config()
        self.create_hotkeys_config()

        # Visual customization
        self.create_css_snippets()

        # Workspace
        self.create_workspace()

        logger.info(f"Obsidian configuration created at {self.obsidian_dir}")

    def create_app_config(self):
        """Create app.json - main application settings"""

        config = {
            # Editor
            "vimMode": False,
            "showLineNumber": True,
            "spellcheck": True,
            "spellcheckLanguages": ["en-US", "de-DE"],
            "strictLineBreaks": False,

            # View modes
            "defaultViewMode": "source",  # or "preview"
            "livePreview": True,

            # Links
            "useMarkdownLinks": False,  # Use [[wikilinks]]
            "newLinkFormat": "shortest",
            "alwaysUpdateLinks": True,

            # Files
            "showFrontmatter": True,
            "foldHeading": True,
            "foldIndent": True,
            "showIndentGuide": True,

            # Attachments
            "attachmentFolderPath": ".attachments",
            "newFileLocation": "folder",

            # Appearance
            "showUnsupportedFiles": False,
            "promptDelete": True
        }

        self._write_json("app.json", config)

    def create_appearance_config(self):
        """Create appearance.json - theme and visual settings"""

        config = {
            "baseFontSize": 16,
            "theme": "obsidian",  # "obsidian" (dark) or "moonstone" (light)
            "cssTheme": "Minimal",  # Popular theme
            "translucency": False,
            "nativeMenus": False,
            "accentColor": ""
        }

        self._write_json("appearance.json", config)

    def create_core_plugins_config(self):
        """Create core-plugins.json - enabled core plugins"""

        plugins = [
            "file-explorer",
            "global-search",
            "switcher",
            "graph",
            "backlink",
            "outgoing-link",
            "tag-pane",
            "page-preview",
            "daily-notes",
            "templates",
            "note-composer",
            "command-palette",
            "editor-status",
            "starred",
            "markdown-importer",
            "word-count",
            "outline",
            "file-recovery"
        ]

        self._write_json("core-plugins.json", plugins)

    def create_community_plugins_config(self):
        """Create community-plugins.json - enabled community plugins"""

        # Note: Users need to install these manually
        # This just enables them once installed
        plugins = [
            "dataview",
            "templater-obsidian",
            "tag-wrangler"
        ]

        self._write_json("community-plugins.json", plugins)

    def create_dataview_config(self):
        """Create Dataview plugin configuration"""

        plugins_dir = self.obsidian_dir / "plugins"
        plugins_dir.mkdir(exist_ok=True)

        dataview_dir = plugins_dir / "dataview"
        dataview_dir.mkdir(exist_ok=True)

        config = {
            "defaultDateFormat": "yyyy-MM-dd",
            "defaultDateTimeFormat": "yyyy-MM-dd HH:mm",
            "maxRecursiveDepth": 4,
            "tableIdColumnName": "File",
            "tableGroupColumnName": "Group",
            "enableInlineDataview": True,
            "enableDataviewJs": True,
            "enableInlineDataviewJs": False,
            "prettyRenderInlineFields": True
        }

        self._write_json(dataview_dir / "data.json", config)

    def create_templater_config(self):
        """Create Templater plugin configuration"""

        plugins_dir = self.obsidian_dir / "plugins"
        templater_dir = plugins_dir / "templater-obsidian"
        templater_dir.mkdir(exist_ok=True)

        config = {
            "template_folder": "Templates",
            "templates_pairs": [["", ""]],
            "trigger_on_file_creation": False,
            "enable_system_commands": False,
            "shell_path": "",
            "script_folder": "",
            "empty_file_template": "",
            "syntax_highlighting": True,
            "enabled": True
        }

        self._write_json(templater_dir / "data.json", config)

    def create_graph_config(self):
        """Create graph.json - graph view settings"""

        config = {
            "collapse-filter": False,
            "search": "",
            "showTags": True,
            "showAttachments": False,
            "hideUnresolved": False,
            "showOrphans": True,
            "collapse-color-groups": False,

            # Color groups for tags
            "colorGroups": [
                {
                    "query": "tag:#tech",
                    "color": {"a": 1, "rgb": 5431378}  # Blue
                },
                {
                    "query": "tag:#business",
                    "color": {"a": 1, "rgb": 14701138}  # Green
                },
                {
                    "query": "tag:#work",
                    "color": {"a": 1, "rgb": 14725458}  # Orange
                },
                {
                    "query": "tag:#personal",
                    "color": {"a": 1, "rgb": 15548997}  # Pink
                },
                {
                    "query": "tag:#reference",
                    "color": {"a": 1, "rgb": 10181046}  # Purple
                }
            ],

            "collapse-display": False,
            "showArrow": True,
            "textFadeMultiplier": 0,
            "nodeSizeMultiplier": 1,
            "lineSizeMultiplier": 1,
            "collapse-forces": False,

            # Force layout settings
            "centerStrength": 0.518713248970312,
            "repelStrength": 10,
            "linkStrength": 1,
            "linkDistance": 250,
            "scale": 1,
            "close": False
        }

        self._write_json("graph.json", config)

    def create_hotkeys_config(self):
        """Create hotkeys.json - keyboard shortcuts"""

        config = {
            # Graph view
            "graph:open": [{"modifiers": ["Mod"], "key": "G"}],

            # Global search
            "global-search:open": [{"modifiers": ["Mod", "Shift"], "key": "F"}],

            # Quick switcher
            "switcher:open": [{"modifiers": ["Mod"], "key": "O"}],

            # Command palette
            "command-palette:open": [{"modifiers": ["Mod", "Shift"], "key": "P"}],

            # Dataview refresh
            "dataview:dataview-force-refresh-views": [
                {"modifiers": ["Mod", "Shift"], "key": "R"}
            ],

            # Daily note
            "daily-notes": [{"modifiers": ["Mod", "Shift"], "key": "D"}]
        }

        self._write_json("hotkeys.json", config)

    def create_css_snippets(self):
        """Create CSS snippets for customization"""

        snippets_dir = self.obsidian_dir / "snippets"
        snippets_dir.mkdir(exist_ok=True)

        # Document type styling
        document_css = """/* RAG-Generated Document Styling */

/* Hierarchical tag colors */
.tag[href="#tech"] {
    background-color: #3498db;
    color: white;
}

.tag[href^="#tech/"] {
    background-color: rgba(52, 152, 219, 0.3);
}

.tag[href="#business"] {
    background-color: #2ecc71;
    color: white;
}

.tag[href^="#business/"] {
    background-color: rgba(46, 204, 113, 0.3);
}

.tag[href="#work"] {
    background-color: #e67e22;
    color: white;
}

.tag[href^="#work/"] {
    background-color: rgba(230, 126, 34, 0.3);
}

.tag[href="#personal"] {
    background-color: #e74c3c;
    color: white;
}

.tag[href^="#personal/"] {
    background-color: rgba(231, 76, 60, 0.3);
}

/* Confidence indicators */
.frontmatter-container {
    border-left: 3px solid #95a5a6;
    padding-left: 10px;
}

/* High confidence documents */
.markdown-preview-view[data-confidence-high] {
    border-top: 2px solid #2ecc71;
}

/* Low confidence documents */
.markdown-preview-view[data-confidence-low] {
    border-top: 2px solid #e74c3c;
}

/* MOC styling */
.mod-header:contains("MOC") {
    color: #3498db;
    font-weight: bold;
}

/* Auto-generated notice */
.markdown-preview-view p:contains("Auto-generated") {
    font-style: italic;
    color: #7f8c8d;
    font-size: 0.9em;
}

/* Dimensional metadata links */
.internal-link[href*="[["] {
    color: #9b59b6;
}

/* Reading time estimate */
.frontmatter-alias {
    color: #95a5a6;
}
"""

        (snippets_dir / "rag-documents.css").write_text(document_css)

        logger.info(f"Created CSS snippets in {snippets_dir}")

    def create_workspace(self):
        """Create default workspace layout"""

        config = {
            "main": {
                "id": "rag-workspace",
                "type": "split",
                "children": [
                    {
                        "id": "file-explorer",
                        "type": "leaf",
                        "state": {
                            "type": "file-explorer",
                            "state": {}
                        }
                    },
                    {
                        "id": "main-editor",
                        "type": "leaf",
                        "state": {
                            "type": "markdown",
                            "state": {
                                "file": "_Index.md",
                                "mode": "source"
                            }
                        }
                    }
                ],
                "direction": "vertical"
            },
            "left": {
                "id": "left-sidebar",
                "type": "split",
                "children": [
                    {
                        "id": "file-explorer-tab",
                        "type": "leaf",
                        "state": {
                            "type": "file-explorer",
                            "state": {}
                        }
                    },
                    {
                        "id": "search-tab",
                        "type": "leaf",
                        "state": {
                            "type": "search",
                            "state": {
                                "query": "",
                                "matchingCase": False,
                                "explainSearch": False,
                                "collapseAll": False,
                                "extraContext": False,
                                "sortOrder": "alphabetical"
                            }
                        }
                    },
                    {
                        "id": "starred-tab",
                        "type": "leaf",
                        "state": {
                            "type": "starred",
                            "state": {}
                        }
                    }
                ],
                "direction": "horizontal",
                "width": 300
            },
            "right": {
                "id": "right-sidebar",
                "type": "split",
                "children": [
                    {
                        "id": "backlink-tab",
                        "type": "leaf",
                        "state": {
                            "type": "backlink",
                            "state": {
                                "collapseAll": False,
                                "extraContext": False,
                                "sortOrder": "alphabetical",
                                "showSearch": False,
                                "searchQuery": "",
                                "backlinkCollapsed": False,
                                "unlinkedCollapsed": True
                            }
                        }
                    },
                    {
                        "id": "outgoing-link-tab",
                        "type": "leaf",
                        "state": {
                            "type": "outgoing-link",
                            "state": {
                                "linksCollapsed": False,
                                "unlinkedCollapsed": True
                            }
                        }
                    },
                    {
                        "id": "tag-tab",
                        "type": "leaf",
                        "state": {
                            "type": "tag",
                            "state": {
                                "sortOrder": "frequency",
                                "useHierarchy": True
                            }
                        }
                    },
                    {
                        "id": "outline-tab",
                        "type": "leaf",
                        "state": {
                            "type": "outline",
                            "state": {}
                        }
                    }
                ],
                "direction": "horizontal",
                "width": 300
            },
            "active": "main-editor",
            "lastOpenFiles": ["_Index.md", "_Dashboard.md"]
        }

        self._write_json("workspace.json", config)

    def _write_json(self, filename: str, data):
        """Helper to write JSON files"""

        file_path = self.obsidian_dir / filename

        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Created {filename}")


def setup_obsidian_vault(vault_path: Path):
    """Complete Obsidian vault setup"""

    configurator = ObsidianConfigurator(vault_path)
    configurator.setup_complete_config()

    # Create folder structure
    folders = [
        "MOCs",
        "Templates",
        ".attachments"
    ]

    for folder in folders:
        (vault_path / folder).mkdir(parents=True, exist_ok=True)

    logger.info(f"Obsidian vault configured at {vault_path}")


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    vault_path = Path("/data/obsidian")
    setup_obsidian_vault(vault_path)

    print("✅ Obsidian vault configured successfully!")
    print(f"   Path: {vault_path}")
    print("   Open this folder in Obsidian to use it.")
