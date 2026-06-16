# Taxonomy Notes

## Purpose

This file is a long-term working document for taxonomy observations and future Taxonomy V2 planning.

MNE now includes Theme Match Audit output, which makes it possible to review the exact keywords and phrases that contributed to theme scores. This file captures observations from real runs before taxonomy changes are made.

Taxonomy changes should be based on repeated evidence rather than isolated examples. Collecting observations first helps distinguish one-off edge cases from recurring false positives, missed matches, overly broad keywords, and conceptual overlap between themes.

These notes support future Taxonomy V2 work by preserving the reasoning behind proposed changes, accepted changes, rejected changes, and implemented changes. The goal is to make taxonomy evolution auditable, deliberate, and grounded in actual MNE output.

## How To Use

Add observations when reviewing Theme Match Audit output, daily reports, saved run JSON, or other real MNE runs.

Useful observations include:

- false positives
- missed matches
- overly broad keywords
- overlapping concepts
- successful taxonomy improvements
- recurring audit findings

Prefer recording concrete evidence before changing taxonomy definitions. Include the theme, headline or observation, matched keyword when available, assessment, possible fix, and current status.

## Observation Template

Date:
Theme:
Headline:
Matched Keyword:
Assessment:
Potential Fix:
Status:

Suggested statuses:

- Monitor
- Under Review
- Approved
- Rejected
- Implemented

## Confirmed Observations

### 2026-06-16

Theme: Energy

Headline:
"The new oil? Inside the effort to turn AI computing power into a tradeable commodity"

Matched Keyword:
oil

Assessment:
Likely false positive.
The article appears primarily AI-related and uses oil as a metaphor.

Potential Fix:
Consider replacing or downgrading broad keyword:

- oil

Potential alternatives:

- crude oil
- brent oil
- oil prices
- oil exports
- oil production
- oil supply

Status:
Monitor

### 2026-06-16

Theme: Rates

Observation:
Longest-match overlap control successfully reduced nested matches.

Example:
"treasury yields" now suppresses overlapping "yields"

Assessment:
Improved scoring quality and reduced double counting.

Status:
Implemented

### 2026-06-16

Theme: AI

Observation:
DeepSeek remains a major AI score driver.

Question:
Is DeepSeek appropriately weighted, or is it dominating AI scores?

Future Consideration:
Possible future split:

- AI software/models
- Semiconductors
- Big Tech

Status:
Monitor

## Taxonomy V2 Ideas

## Approved Changes

## Implemented Changes
