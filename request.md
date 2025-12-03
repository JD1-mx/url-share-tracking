n8n:
A form with a dropdown
The selected truck id value gets added to a sheet
Share link is provided


Stop sharing link:
A form dropdown 
The selected truck id is removed from the sheet
The share link no longer works


The sheet is ‘looked up as the available ids in the dropdown to track on stream lit


list with truck ids - IFFCO
https://docs.google.com/spreadsheets/d/1v6nVIvSm-Lg685aYponZVnopSmQYGdyvpjXpY39fQ3c/edit?usp=sharing

these are the columns:
device_id	plate_number	time_added

when a vehicle is selected from the dropdown on streamlit a map is displayed from the time the vehicle was added.
it queries a collection named 'device_histories' which is a collection with historical documents of the lcoation of that vehicle
so this allows the streamlit user visualize the path of the truck

(for now create a dummy data of this device_histories)