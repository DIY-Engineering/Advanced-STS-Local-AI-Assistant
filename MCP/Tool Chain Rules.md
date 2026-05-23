TOOL EXECUTION RESULTS
{separator}

Original user query: "{original_query}"

Tool execution results:
{results_text}

{separator}
INSTRUCTIONS:
{separator}

Based on these results and the original query you must decide:

IF you need to to play a youtube video:
   → First use "youtube_search" with the video title provided by the user or a description of the video content
   → Then use "youtube_play" to open that video in the default web browser

IF you you need to search for weather:
   → Search on Google for the weather on the location specified by the user
   → Fetch the first google result and extract the relevant information (Temperature in °C , wind speed, UV Index, Visibility & Atmospheric Conditions)

IF you need to make web search:
   → Use "google_search" with the quiry provided by user
   → Fetch the first web result, extract the relevant information and present it to the user

DO NOT include JSON in your final response!!!
NOW, based on the tool results above, what is your response?
