# MNE UI Naming Framework

Public labels translate persisted engine concepts at the presentation boundary. Engine names remain canonical. A label is displayed only when the shown value has an exact, honest backing field.

## Keep and map

| Public label | Backing | Usage |
|---|---|---|
| X-Ray View | Native disclosure over existing persisted explanation/evidence | Deeper support and limitations |
| Market Reaction | `market_expression_context` and its role-classified instruments | Descriptive price/sector expression |
| Narrative Pulse | Literal persisted `narrative_pulse` lifecycle metric only | Never a general movement heading |
| Narrative Direction | Existing Pulse plus acceleration/rotation presentation context | Broad strengthening, fading, or stability context |
| Recent Movement | Existing share delta and rotation history | Recent change context |
| Daily Launch Line | Latest persisted daily candle `open` | Reference for the latest verified session's behavior |

`Narrative Gravity` is not implemented. Neither `concentration_gap` nor leadership rotation is an exact persisted measure of concentration of attention around the leading narrative.

## Avoid

Do not introduce predictive, promotional, or unverifiable labels such as “Smart Money Reality,” automatic “Fact Check,” “Hype Meter,” trade recommendation, target price, or scoring claims on the user surface.

## Reserved — not implemented

- **Attention Velocity:** reserved until a persisted rate-of-change field exists. Crowding/Attention is a level, not velocity.
- **Primary-Source Support:** reserved until general primary/secondary source classification is persisted and surfaced.

These terms must not appear as placeholder UI, fabricated states, gauges, or untranslated passthroughs.
