# 5HVLED Stream Attendance

A local Twitch attendance and end-credits system for **Streamer.bot + OBS Studio**.

It automatically tracks who showed up, who was absent, attendance streaks, timeout eligibility, and 24-hour session end credits — while keeping the dashboard local to the streaming PC.

## Features

- Automatic attendance from Twitch **First Words**
- Automatic absences when an attendance session closes
- **24-hour session continuity**: restart the stream within 24 hours and the same session reopens
- Permanent attendance and absence history
- Viewer `!attendance` and `!atd` commands
- Current attendance streaks
- Timeout eligibility every 5 cumulative absences
- No automatic timeout — viewers only get a public "mods' mercy" warning
- Local web dashboard with 1-second live refresh while visible
- Manual corrections, punishment records, audit log, backup and reset tools
- 24-hour end credits containing attendees, new followers, subscribers and donors
- End credits persist across stream restarts in the same attendance session
- Streamlabs, Ko-fi, Fourthwall and TipeeeStream donation triggers included
- OBS-ready `end-credits.txt`
- User-friendly Windows installer

## Requirements

- Windows 10 or Windows 11
- OBS Studio
- Streamer.bot
- Twitch connected to Streamer.bot
- Internet access during the first install so Python/Flask can be installed if needed

## Quick install

1. Download the latest ZIP from **Releases**.
2. Extract it.
3. Run `INSTALL.bat`.
4. Enter your channel/brand name and Twitch handle when prompted.
5. Import `5HVLED-Stream-Attendance-All-In-One.sb` into Streamer.bot.
6. Make sure Twitch and OBS are connected in Streamer.bot.
7. Done.

The installer places the system under:

```text
Documents\5HVLED-Attendance\
```

## OBS end credits

Add a **Text (GDI+)** source in OBS, enable **Read from file**, and select:

```text
Documents\5HVLED-Attendance\end-credits.txt
```

Add an OBS Scroll filter if you want rolling credits.

## Streamer.bot actions

### Stream Attendance

- Attendance - Stream Started
- Attendance - Viewer Check-In
- Attendance - Stream Stopped
- Attendance - Check My Stats

### Stream End Credits

- Credits - Sync 24H Session
- Credits - Attendee
- Credits - New Follower
- Credits - Subscriber
- Credits - Donor

## Viewer command

```text
!attendance
```

or:

```text
!atd
```

Example reply:

```text
@viewer ✅ Attended: 12 | ❌ Absent: 3 | 🔥 Current streak: 4
```

## Privacy

The dashboard binds to `127.0.0.1` only. By default, the web interface is available only on the local PC and is not exposed to the internet.

## Notes

- The app uses port `6767`.
- If multiple OBS connections exist in Streamer.bot, select the intended connection on the imported OBS triggers.
- `RESET_ALL_DATA.bat` permanently clears attendance and current credits data after an explicit confirmation.
- `BACKUP_DATA.bat` creates timestamped backups in `Documents\5HVLED-Attendance-Backups\`.

## Credits

Created by **5HVLED** for the streaming community.
