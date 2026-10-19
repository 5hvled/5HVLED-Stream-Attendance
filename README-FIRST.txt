5HVLED STREAM ATTENDANCE — COMPLETE FRIEND VERSION
================================================

QUICK INSTALL
1. Extract the ZIP.
2. Double-click INSTALL.bat.
3. Enter your channel / brand name and Twitch handle.
4. Let the installer finish.
5. In Streamer.bot, open Import and import:
   5HVLED-Stream-Attendance-All-In-One.sb
6. Make sure Twitch and OBS are connected in Streamer.bot.
7. Done.

The installer puts everything here automatically:
  Documents\5HVLED-Attendance\

WHAT'S INCLUDED
- Local attendance website / dashboard.
- Automatic server startup when OBS starts streaming.
- Automatic 24-hour attendance sessions.
- If the stream restarts less than 24 hours after the last stop, the SAME session reopens.
- First Words automatically marks a viewer present.
- Missing tracked viewers are marked absent when the stream stops.
- Permanent attendance / absence history.
- Timeout eligibility every 5 cumulative absences.
- No automatic timeout: eligible viewers only get the public "mods' mercy" warning.
- Manual punishment records and manual adjustments in the dashboard.
- Dashboard data refreshes every second while the tab is visible.
- !attendance and !atd commands:
    @viewer ✅ Attended: 12 | ❌ Absent: 3 | 🔥 Current streak: 4
- 24-hour-session end credits with attendees, new followers, subscribers and donors.
- Credits carry across stream restarts in the same 24-hour attendance session.
- Credits automatically reset only when a genuinely new attendance session is created.
- 10 blank lines at the end of the credits file for clean OBS scrolling loops.
- Backup and full-data reset utilities.

END CREDITS IN OBS
1. Add a Text (GDI+) source.
2. Enable "Read from file".
3. Select:
   Documents\5HVLED-Attendance\end-credits.txt
4. Add an OBS Scroll filter if you want rolling credits.

DONATION EVENTS INCLUDED
The donor credits action contains triggers for:
- Streamlabs
- Ko-fi
- Fourthwall
- TipeeeStream

If a friend uses a different donation service, they can add that service's donation trigger to the existing "Credits - Donor" action.

STREAMER.BOT ACTIONS INCLUDED
Group: Stream Attendance
- Attendance - Stream Started
- Attendance - Viewer Check-In
- Attendance - Stream Stopped
- Attendance - Check My Stats

Group: Stream End Credits
- Credits - Sync 24H Session
- Credits - Attendee
- Credits - New Follower
- Credits - Subscriber
- Credits - Donor

HELPFUL FILES AFTER INSTALL
Documents\5HVLED-Attendance\start_server.bat
Documents\5HVLED-Attendance\stop_server.bat
Documents\5HVLED-Attendance\RESET_ALL_DATA.bat
Documents\5HVLED-Attendance\BACKUP_DATA.bat
Documents\5HVLED-Attendance\end-credits.txt
Documents\5HVLED-Attendance\attendance.db

RESET WARNING
RESET_ALL_DATA.bat permanently clears attendance.db and current end-credit session data.
It asks you to type RESET before it does anything.

BACKUPS
BACKUP_DATA.bat makes a timestamped copy under:
  Documents\5HVLED-Attendance-Backups\

NETWORK / PRIVACY
The website listens only on 127.0.0.1 (the local PC). It is not exposed to the internet by the app.

REQUIREMENTS
- Windows 10/11
- Streamer.bot
- OBS Studio
- Twitch connected to Streamer.bot
- Internet during first installation so Python / Flask can be installed if needed

NOTES
- OBS trigger imports are intentionally not tied to a specific OBS connection ID, making the package portable.
  If a user has multiple OBS connections in Streamer.bot, they may need to select the intended connection on the OBS triggers after import.
- The app uses port 6767. Another program using that port will conflict.
