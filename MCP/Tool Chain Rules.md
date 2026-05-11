TOOL EXECUTION RESULTS

{separator}



Original user query: "{original\_query}"



Tool execution results:

{results\_text}



{separator}

INSTRUCTIONS:

{separator}



Based on these results, you must decide:



1\. IF you need MORE information:

&#x20;  → Call another tool (e.g., web\_fetch if you just got URLs from web\_search)

&#x20;  → Respond with JSON tool call



2\. IF you have ENOUGH information:

&#x20;  → Extract the relevant answer from the results

&#x20;  → Provide a clear, natural language response to the user

&#x20;  → DO NOT include JSON in your response



EXAMPLES:



Example 1 - Need more info:

Results: web\_search returned URLs about weather

Your response: {{"id": "xyz", "tool": "web\_fetch", "arguments": {{"url": "first\_url\_here"}}}}



Example 2 - Have enough info:

Results: web\_fetch returned page content with "Temperature: 15°C, Cloudy"

Your response: "The temperature in Bucharest is 15°C and it's cloudy."



NOW, based on the tool results above, what is your response?

