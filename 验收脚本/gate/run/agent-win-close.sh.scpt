on run argv
  set theTty to item 1 of argv
  set hitCount to 0
  tell application "Terminal"
    repeat with i from (count of windows) to 1 by -1
      try
        if (tty of tab 1 of window i) is theTty then
          close window i saving no
          set hitCount to hitCount + 1
        end if
      end try
    end repeat
  end tell
  return "closed x " & hitCount
end run
