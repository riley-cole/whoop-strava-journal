# Journal Tagging & Linking Convention

Reference for all metadata applied to Obsidian journal entries, whether manual or automated.

## Frontmatter Arrays

| Field | Source | Format | Example |
|-------|--------|--------|---------|
| `tags:` | Manual + auto (recovery zone) | Plain strings | `journal/work`, `recovery/green` |
| `people:` | Auto-detected + manual | Wikilinks | `"[[Alice]]"`, `"[[Bob]]"` |
| `places:` | Auto-detected + manual | Wikilinks | `"[[Portland]]"` |
| `projects:` | Auto-detected + manual | Wikilinks | `"[[My Project]]"`, `"[[Side Hustle]]"` |

**Auto-detection:** The sync script scans body text for `[[WikiLink]]` patterns and matches against the `people`, `places`, and `projects` lists in `~/.whoop-journal/config.json`. Matched entries are added to the corresponding frontmatter arrays automatically. Manual entries not in the config lists are preserved.

## Frontmatter Tags

Tags go in the `tags:` array. Mix of manual (you add them) and automated (sync adds them).

| Tag | When | Source |
|-----|------|--------|
| `journal` | Every entry | Template default |
| `journal/family` | Family-focused content | Manual |
| `journal/work` | Work-focused content | Manual |
| `journal/milestone` | Significant day | Manual |
| `journal/parenting` | Parenting moments | Manual |
| `recovery/green` | Whoop recovery 67-100% | Auto (sync) |
| `recovery/yellow` | Whoop recovery 34-66% | Auto (sync) |
| `recovery/red` | Whoop recovery 0-33% | Auto (sync) |

Recovery tags are mutually exclusive. The sync script removes stale recovery tags if the score changes on re-sync.

### Dataview queries

```dataview
TABLE whoop-recovery, whoop-strain, whoop-sleep-hours
FROM "Journal"
WHERE contains(tags, "recovery/red")
SORT date DESC
```

```dataview
TABLE date, whoop-recovery
FROM "Journal"
WHERE contains(tags, "recovery/green") AND contains(tags, "journal/work")
SORT date DESC
```

## Inline Moment Tags

Placed at the end of the relevant sentence or paragraph in the body text. These are manual and intentional.

| Tag | When to use |
|-----|-------------|
| `#decision` | A choice was made. Picking a tech stack, saying yes to something. |
| `#milestone` | Something notable happened for the first time. First journal entry, a product launch. |
| `#idea` | A concept worth revisiting later. Product ideas, feature concepts, things to explore. |
| `#lesson` | Something learned the hard way. Mistakes, surprises, things that didn't go as expected. |
| `#reflection` | Personal introspection. Thinking about direction, mindset, feelings. |
| `#gratitude` | Thankfulness. Used in the "Grateful for" section. |

These tags are searchable in Obsidian's tag pane and via Dataview. They create a cross-cutting view across all journal entries.

## Wikilinks in Body Text

Link liberally. Every named entity that might appear more than once gets brackets.

| Category | Examples |
|----------|----------|
| People | `[[Alice]]`, `[[Bob]]`, `[[Carol]]` |
| Places | `[[Portland]]`, `[[Tokyo]]`, `[[Central Park]]` |
| Projects / Companies | `[[My Startup]]`, `[[Side Project]]`, `[[Acme Corp]]` |
| Tools / Products | `[[Obsidian]]`, `[[Claude]]`, `[[Xcode]]` |

These feed the Obsidian graph view and create backlink pages. Even if the target note doesn't exist yet, the link is useful — Obsidian tracks unresolved links.

## Config: Known Entities

Auto-detection lists live in `~/.whoop-journal/config.json`:

```json
{
  "people": ["Alice", "Bob", "Carol"],
  "places": ["Portland", "Tokyo", "Central Park"],
  "projects": ["My Startup", "Side Project", "Acme Corp"]
}
```

Update these lists as new people, places, or projects appear in your journal entries. Names must match the wikilink text exactly (case-sensitive).
