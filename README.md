# Lettuce Eat Together 🥬

A family food diary for shared meal logging, individual calorie goals, and supportive progress. Good food, good goals, great company.

## Features

- Separate username and password accounts for each family member.
- Create a new household or join one with an invitation code.
- Passwords are stored as salted PBKDF2 hashes, never as plain text.
- Each person edits their own food preferences and calorie-goal profile.
- Household members can view one another's daily calorie and macro intake and logged meals.
- Each member can add or remove only their own food-log entries.
- Automatic food calories and macros, personal calorie goals, and supportive family notes.
- Cuisine-first family and personal recommendations, with dishes filtered for each member's diet and allergies.
- Curry suggestions include compatible bread or side pairings, and recipe cards include quick preparation steps.
- Expanded the local catalogue to 78 dishes across 11 cuisines.
- SQLite storage in `data/nutrition.db`; no separate SQL server is needed.
- A polished diary-first dashboard with compact family progress and meal summaries.

## Run on Windows

Open PowerShell in this project folder and run:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Using `python -m streamlit` works even when the `streamlit` command is not on the Windows PATH. If you use a virtual environment, activate it before running these commands.

## Create family accounts

1. Open the app and choose **Create account / Join family**.
2. The first person enters a family name and leaves the invite-code field blank. This creates the household and an owner account.
3. The owner opens **Invite family members** in the sidebar and shares the code privately.
4. Each other person creates their own account with that invite code.
5. Each member signs in with their own username and password. The **Today** dashboard shows household intake, while profile edits and food-log deletion are limited to the signed-in member.

Use a different username for every account. Account names must be unique within a household.

## Data and privacy

The SQLite database is saved at `data/nutrition.db`. Back up that file to back up accounts and nutrition records. The app does not include password reset, account deletion, login rate limiting, or email verification yet.

This app is currently a local prototype. Family members can use it from different devices only after it is deployed to a shared host. Do not expose the local development server directly to the public internet; a public deployment needs HTTPS and additional operational security.

Existing JSON profile and diary files are left untouched, but this version does not import them automatically. After creating accounts, members should enter their own profile and goal details again.

## Calorie estimate

Automatic goals are approximate adult estimates using Mifflin–St Jeor, activity level, and the selected weekly pace. Equal current and goal weights force maintenance. Estimates below 1,000 kcal/day are hidden. The estimate is not medical advice and is not for people under 18 or who are pregnant or breastfeeding.
