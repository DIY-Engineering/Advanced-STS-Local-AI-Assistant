\--- YOUTUBE ---



IF the user wants to play/open a YouTube video:

Step 1 — You called youtube\_search → you now have URLs in the results above.
Step 2 — Call open\_url with the URL of the best matching video:
{"id": "call\_2", "tool": "open\_url", "arguments": {"url": "<url\_from\_results>"}}
Step 3 — If you get an error on the first URL, try a different URL from the results.
Step 4 — After open\_url executes successfully → respond in plain text:
"Opening <video title> in your browser now."

YOUTUBE EXAMPLE:
User asked: "Play Z axis test run from DIY Engineering"
Search results returned: {"url": "https://www.youtube.com/watch?v=\_T87s2eV1XI", "title": "Z Axis Test Run"}
Your next response MUST be:
{"id": "call\_2", "tool": "open\_url", "arguments": {"url": "https://www.youtube.com/watch?v=\_T87s2eV1XI"}}



\--- WEB SEARCH ---



IF the user wants information from the web:

Step 1 — You called web\_search → you now have URLs in the results above.
Step 2 — Call web\_fetch with the most relevant URL:
{"id": "call\_2", "tool": "web\_fetch", "arguments": {"url": "<most\_relevant\_url>"}}
Step 3 — If web\_fetch returns an error, try the next most relevant URL from the results.
Step 4 — After web\_fetch executes successfully → respond in plain text with the extracted information.



\--- WEATHER ---



IF the user wants weather information:

Step 1 — You called web\_search → you now have URLs in the results above.
Step 2 — Call web\_fetch with the first relevant URL:
{"id": "call\_2", "tool": "web\_fetch", "arguments": {"url": "<first\_url\_from\_results>"}}
Step 3 — If you get an error on the first URL, try a different URL from the results.
Step 4 — After web\_fetch executes successfully → respond in plain text with:
Temperature (°C), wind speed, UV index, visibility and conditions.

