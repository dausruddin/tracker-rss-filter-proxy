import re
import config
from flask import Flask, request, jsonify
import httpx
import xml.etree.ElementTree as ET

app = Flask(__name__)

def parse_size(size_str, size_filter):
    # Use the provided regex pattern to search for the size and unit in size_str
    match = re.search(size_filter, size_str, re.IGNORECASE)
    
    # If no match is found, return None
    if not match:
        return None
    
    # Extract the numeric value from the match (group 1)
    value = float(match.group(1))
    
    # Extract the unit from the match (group 3)
    unit = match.group(2)
    
    # Convert the extracted size to MiB based on the unit
    if unit == 'GB' or unit == 'GiB':
        return value * 1024  # Convert GB or GiB to MiB
    elif unit == 'MB' or unit == 'MiB':
        return value  # Already in MB or MiB, convert to MiB
    
    return None


@app.route('/rss', methods=['GET'])
def get_data():
    source = request.args.get('source')
    key = request.args.get('key')
    
    if not source or not key:
        return jsonify({"error": "Both 'source' and 'key' parameters are required"}), 400
    
    if key != config.PASSWORD:
        return jsonify({"error": "Invalid key"}), 403
    
    data = config.SOURCES.get(source)
    if not data:
        return jsonify({"error": f"Source '{source}' not found"}), 404
    
    try:
        response = httpx.get(data['rss'])
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            
            # Create a new root element for the filtered items
            channel = root.find('channel')
            new_channel = ET.Element('channel')
            
            # Copy non-item elements from the original channel
            for child in channel:
                if child.tag != 'item':
                    new_channel.append(child)
            
            items = channel.findall('.//item')

            if not items:
                return jsonify({"error": f"No items found in source '{source}'"}), 404
            
            # Iterate over each item and apply the filter
            for item in items:
                content = item.find(data['field'])
                if content is not None and content.text:
                    size_mib = parse_size(content.text, data['filter'])
                    if size_mib is not None:
                        min_size_mib = data.get('min_size_mib', 0)
                        max_size_mib = data.get('max_size_mib', float('inf'))
                        
                        # Check if the size falls within the specified range
                        if min_size_mib <= size_mib <= max_size_mib:
                            new_channel.append(item)  # Add matched items to the new channel
            
            # Create a new RSS root element
            rss_root = ET.Element('rss', {'version': '2.0'})
            rss_root.append(new_channel)

            # Convert the filtered XML back to string
            return ET.tostring(rss_root, encoding='unicode')
            
        else:
            return jsonify({"error": f"Failed to fetch data from source '{source}': {response.status_code}"}), response.status_code
        
    except httpx.RequestError as e:
        return jsonify({"error": f"HTTP request failed for source '{source}': {e}"}), 500

if __name__ == '__main__':
    app.run(host=config.HOST, port=config.PORT)
