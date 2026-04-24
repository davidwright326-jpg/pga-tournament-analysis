# Requirements: PGA Tournament Analysis Tool

## Overview
A web application that automatically identifies the key statistical categories needed to win the current week's PGA Tour tournament (based on course characteristics and historical winner profiles) and generates a ranked list of players most likely to perform well based on those stats.

## Data Sources
- **PGA Tour public stats** (pgatour.com/stats): Player statistics across all categories (Strokes Gained, Off the Tee, Approach, Around the Green, Putting, Scoring)
- **PGA Tour tournament schedule & course data**: Current week's tournament, course info, and past results
- **ESPN public golf endpoints**: Supplementary player/tournament data
- **DataGolf (optional, paid API)**: Enhanced historical round-level data and course fit analysis — can be integrated later as a premium data source

## User Stories

### 1. View Current Tournament Context
As a user, I want to see the current week's PGA Tour tournament details (name, course, dates, par, yardage) so I understand the event being analyzed.

#### Acceptance Criteria
- 1.1 The dashboard displays the current week's tournament name, course name, dates, and basic course info (par, yardage)
- 1.2 Tournament context updates automatically each week when the PGA Tour schedule advances
- 1.3 If no tournament is scheduled for the current week, the system displays a message indicating the next upcoming event

### 2. Identify Key Stats for the Course
As a user, I want the system to determine which statistical categories are most important for success at the current week's course, so I can understand what it takes to win there.

#### Acceptance Criteria
- 2.1 The system analyzes historical winner/top-finisher data at the current course to identify which stat categories correlate most with success
- 2.2 Key stats are ranked by importance with a weight/score indicating relative significance
- 2.3 The analysis considers at minimum: SG: Off-the-Tee, SG: Approach, SG: Around-the-Green, SG: Putting, Driving Distance, Driving Accuracy, Greens in Regulation, Scrambling, Birdie Average
- 2.4 The system displays a clear breakdown of why each stat matters for this specific course (e.g., "Narrow fairways favor driving accuracy over distance")
- 2.5 If insufficient historical data exists for a course, the system falls back to analyzing similar course archetypes

### 3. Generate Player Rankings
As a user, I want to see a ranked list of players who best match the key stats profile for the current week's tournament, so I can identify top picks.

#### Acceptance Criteria
- 3.1 The system generates a ranked list of at least 20 players sorted by their composite fit score for the current tournament
- 3.2 Each player entry shows their name, current world/FedEx ranking, composite fit score, and individual stat values for each key category
- 3.3 The composite fit score is calculated by weighting each player's stats according to the importance weights from the course analysis
- 3.4 Player stats reflect recent form (current season stats with recency weighting)
- 3.5 Users can filter the player list by minimum world ranking, specific stat thresholds, or tournament field membership

### 4. Dashboard Visualization
As a user, I want an interactive web dashboard to explore the analysis, so I can dig into the data visually.

#### Acceptance Criteria
- 4.1 The dashboard has a clean, responsive layout that works on desktop and tablet
- 4.2 The course stats importance is displayed as a visual chart (bar chart or radar chart)
- 4.3 The player rankings table is sortable by any column
- 4.4 Clicking a player shows a detailed profile with their stats compared to the course ideal
- 4.5 The dashboard includes a "last updated" timestamp showing data freshness

### 5. Automatic Weekly Updates
As a user, I want the data to refresh automatically each week so the analysis is always current.

#### Acceptance Criteria
- 5.1 The system runs a scheduled data refresh job (at minimum weekly, before the tournament starts — e.g., Monday or Tuesday)
- 5.2 The refresh pulls updated player stats and the new tournament/course info
- 5.3 Historical analysis is recalculated when the tournament changes
- 5.4 The system logs refresh status and surfaces errors if data fetching fails
- 5.5 Users can manually trigger a data refresh from the dashboard

### 6. Course History & Comparison
As a user, I want to see how past winners at this course performed statistically, so I can validate the model's stat selections.

#### Acceptance Criteria
- 6.1 The dashboard shows a table of past winners (last 5-10 years) at the current course with their key stats from that tournament week
- 6.2 Users can compare any player's current stats against the historical winner profile
- 6.3 The system highlights stat categories where a player significantly exceeds or falls short of the historical winner average
