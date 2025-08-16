'use strict';
/**
 *  dash.js
 *  https://github.com/Zalgar/xrit-rx-docker
 *  
 *  Updates dashboard data through xrit-rx API
 *  Enhanced with real-time progress tracking and partial image display
 *
 *  Original work by sam210723: https://github.com/sam210723/xrit-rx
 */

var config = {};
var blocks = {
    vchan:    {
        width: 620,
        height: 180,
        title: "Virtual Channel",
        update: block_vchan
    },
    time:     {
        width: 390,
        height: 180,
        title: "Time",
        update: null
    },
    latestimg:  {
        width: 500,
        height: 590,
        title: "Latest Image",
        update: block_latestimg
    },
    schedule: {
        width: 510,
        height: 590,
        title: "Schedule",
        update: block_schedule
    },
    progress: {
        width: 420,
        height: 300,
        title: "Download Progress",
        update: block_progress
    }
};
var vchans = {
    "GK-2A": {
        0:  ["FD", "Full Disk"],
        4:  ["ANT", "Alpha-numeric Text"],
        5:  ["ADD", "Additional Data"],
        63: ["IDLE", "Fill Data"]
    }
};
var sch = [];
var current_vcid;
var latest_image;
var current_progress = {};
var partial_images = {};
var utc_date;

function init()
{
    print("Starting xrit-rx dashboard...", "DASH");

    // Get config object from xrit-rx
    http_get("/api", (res) => {
        if (res.status == 200) {
            res.json().then((data) => {
                config = data;
                
                // Configure dashboard
                if (!configure()) { return; }
                
                // Load available timelapses
                loadTimelapses();
                
                // Load latest 3hr timelapse
                loadLatestTimelapse();
                
                print("Ready", "DASH");
            })
        }
        else {
            print("Failed to get configuration", "CONF");
            return false;
        }
    });
}


/**
 * Configure dashboard
 */
function configure()
{
    // Write config object to console
    console.log(config);

    // Set heading and window title
    var heading = document.getElementById("dash-heading");
    heading.innerHTML =  `${config.spacecraft} ${config.downlink} Dashboard`;
    heading.innerHTML += `<span><a href="api-docs.html" style="color: #777; text-decoration: none; margin-right: 20px;">API Docs</a>xrit-rx <a href="https://github.com/Zalgar/xrit-rx-docker/releases/tag/v${config.version}" target="_blank" title="Release notes on GitHub">v${config.version}</a></span>`;
    document.title = `${config.spacecraft} ${config.downlink} - xrit-rx v${config.version}`;

    // Build blocks
    console.log(blocks);
    for (var block in blocks) {
        var el = document.getElementById(`block-${block}`);
        blocks[block].body = el.children[1];
        
        // Set block size
        el.style.width  = `${blocks[block].width}px`;
        el.style.height = `${blocks[block].height}px`;

        // Set block heading
        el.children[0].innerText = blocks[block].title;
    }

    // Parse and build schedule
    if (config.spacecraft == "GK-2A") { get_schedule() };

    // Setup clock loop
    setInterval(() => {
        block_time(blocks.time.body);
    }, 100);
    block_time(blocks.time.body);

    // Setup polling loop
    setInterval(poll, config.interval * 1000);
    poll();
    poll();

    return true;
}


/**
 * Poll xrit-rx API for updated data
 */
function poll()
{
    // Get current VCID
    http_get("/api/current/vcid", (res) => {
        if (res.status == 200) {
            res.json().then((data) => {
                current_vcid = data['vcid'];
            });
        }
        else {
            print("Failed to get current VCID", "POLL");
            return false;
        }
    });

    // Get last image
    http_get("/api/latest/image", (res) => {
        if (res.status == 200) {
            res.json().then((data) => {
                latest_image = data['image'];
            });
        }
        else {
            print("Failed to get last image", "POLL");
            return false;
        }
    });

    // Get current progress
    http_get("/api/current/progress", (res) => {
        if (res.status == 200) {
            res.json().then((data) => {
                current_progress = data['active_downloads'];
            });
        }
        else {
            print("Failed to get current progress", "POLL");
            return false;
        }
    });

    // Get partial images
    http_get("/api/current/partial", (res) => {
        if (res.status == 200) {
            res.json().then((data) => {
                partial_images = data['partial_images'];
            });
        }
        else {
            print("Failed to get partial images", "POLL");
            return false;
        }
    });

    // Call update function for each block
    for (var block in blocks) {
        if (blocks[block].update != null) {
            blocks[block].update(blocks[block].body);
        }
    }
}


/**
 * Download and parse schedule
 */
function get_schedule()
{
    // Get UTC date
    var d = new Date();
    utc_date = `${d.getUTCFullYear()}${(d.getUTCMonth()+1).toString().padStart(2, "0")}${d.getUTCDate().toString().padStart(2, "0")}`;

    /**
     * Schedule download is proxied through my web server at vksdr.com because KMA 
     * have not included CORS headers in their API. Mordern browsers will disallow 
     * cross-domain requests unless these headers are present. The PHP backend of 
     * my web server will make the request to the KMA API then return the result to 
     * the dashboard with the necesary CORS headers.
     * 
     * See https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS
     */

    // Build request URL
    var url = "https://vksdr.com/scripts/kma-dop.php";
    var params = `?searchDate=${utc_date}&searchType=${config.downlink}`;

    http_get(url + params, (res) => {
        if (res.status == 200) {
            res.json().then((data) => {
                var raw = data['data'];
                var start = -1;
                var end = -1;

                // Find start and end of DOP
                for (var i in raw) {
                    var line = raw[i].trim();

                    if (line.startsWith("TIME(UTC)")) {
                        start = parseInt(i) + 1;
                    }

                    if (line.startsWith("ABBREVIATIONS:")) {
                        end = parseInt(i) - 2;
                    }
                }

                // Loop through schedule entries
                for (var i = start; i <= end; i++) {
                    var line = raw[i].trim().split('\t');
                    var entry = [];

                    entry[0] = line[0].substring(0, line[0].indexOf("-"));
                    entry[1] = line[0].substring(line[0].indexOf("-") + 1);
                    entry[2] = line[1].substring(0, line[1].length - 3);
                    entry[3] = line[1].substring(line[1].length - 3);
                    entry[4] = line[2];
                    entry[5] = line[3] == "O";

                    if (entry[2] == "EGMSG") { continue; }   // Skip EGMSG

                    sch.push(entry);
                }

                // Create schedule table
                var table = document.createElement("table");
                table.className = "schedule";
                table.appendChild(document.createElement("tbody"));

                // Table header
                var header = table.createTHead();
                var row = header.insertRow(0);
                row.insertCell(0).innerHTML = "Start (UTC)";
                row.insertCell(1).innerHTML = "End (UTC)";
                row.insertCell(2).innerHTML = "Type";
                row.insertCell(3).innerHTML = "ID";

                // Add table to document
                var element = blocks['schedule'].body;
                element.innerHTML = "";
                element.appendChild(table);

                print("Ready", "SCHD");
            });
        }
        else {
            print("Failed to get schedule", "SCHD");
            return false;
        }
    });
}


/**
 * Update Virtual Channel block
 */
function block_vchan(element)
{
    // Check block has been built
    if (element.innerHTML == "") {
        for (var ch in vchans[config.spacecraft]) {
            var indicator = document.createElement("span");
            indicator.className = "vchan";
            indicator.id = `vcid-${ch}`
            indicator.title = vchans[config.spacecraft][ch][1];

            var name = vchans[config.spacecraft][ch][0];
            indicator.innerHTML = `<span>${name}</span><p>VCID ${ch}</p>`;

            // Set 'disabled' attribute on blacklisted VCIDs
            if (config.vcid_blacklist.indexOf(parseInt(ch)) > -1) {
                indicator.setAttribute("disabled", "");
                indicator.title += " (blacklisted)";
            }

            element.appendChild(indicator);
        }
    }
    else {  // Update block
        for (var ch in vchans[config.spacecraft]) {
            // Do not update blacklisted channels
            if (config.vcid_blacklist.indexOf(parseInt(ch)) > -1) { continue; }

            // Update active channel
            if (ch == current_vcid) {
                document.getElementById(`vcid-${ch}`).setAttribute("active", "");
            }
            else {
                document.getElementById(`vcid-${ch}`).removeAttribute("active");
            }
        }
    }
}


/**
 * Update Time block
 */
function block_time(element)
{
    var local = element.children[0];
    var utc = element.children[1];

    local.innerHTML = `${get_time_local()}<br><span title="UTC ${get_time_utc_offset()}">Local</span>`;
    utc.innerHTML = `${get_time_utc()}<br><span>UTC</span>`;
}


/**
 * Update Latest Image block
 */
function block_latestimg(element)
{
    var img = element.children[0].children[0];
    var link = element.children[0];
    var cap = element.children[2];
    
    // Check for partial images first (prioritize active downloads)
    var partial_fd = partial_images['FD'];
    var has_partial = partial_fd && partial_fd.path;
    
    if (has_partial) {
        var url = `/api/latest/fd/partial`;
        var fname = `${partial_fd.product_name}_partial (${partial_fd.segments}/${partial_fd.total_segments} segments)`;
        
        // Set <img> src attribute for partial image
        if (img.getAttribute("src") != url) {
            img.setAttribute("src", url);
            link.setAttribute("href", url);
            cap.innerText = fname;
            cap.style.color = "#FFA500"; // Orange color to indicate partial
        }
    }
    else if (latest_image) {
        var url = `/api/${latest_image}`;
        var fname = url.split('/');
        fname = fname[fname.length - 1];
        var ext = fname.split('.')[1];
        fname = fname.split('.')[0];

        // Set <img> src attribute for completed image
        if (ext != "txt") {
            // Only update image element if URL has changed
            if (img.getAttribute("src") != url) {
                img.setAttribute("src", url);
                link.setAttribute("href", url);
                cap.innerText = fname;
                cap.style.color = ""; // Reset color for completed images
            }
        }
    }
    else {
        // Check image output is enabled
        if (config.images == false) {
            cap.innerHTML = "Image output is disabled in xrit-rx<br><br>Check key file is present and <code>images = true</code> in <code>xrit-rx.ini</code> configuration file";
        }
        else {
            link.innerHTML = "<img class=\"latestimg\">";
            link.setAttribute("href", "#");
            cap.innerText = "Waiting for image...";
        }
    }
}


/**
 * Update Schedule block
 */
function block_schedule(element)
{
    // Check schedule has been loaded
    if (sch.length == 0) { return; }

    // Add spacecraft and downlink to block header
    var header = element.parentNode.children[0];
    header.innerHTML = `${config.spacecraft} ${config.downlink} Schedule`;

    // Check UTC date
    var d = new Date();
    if (utc_date != `${d.getUTCFullYear()}${(d.getUTCMonth()+1).toString().padStart(2, "0")}${d.getUTCDate().toString().padStart(2, "0")}`) {
        location.reload();
    }
    
    // Get current UTC time
    var time = get_time_utc().replace(/:/g, "");

    // Get table body element
    var body = element.children[0].children[1];

    // Find first entry to add to table
    var first;
    for (var entry in sch) {
        var start = sch[entry][0];
        var end = sch[entry][1];

        if (time < start) {
            first = Math.max(0, parseInt(entry) - 3);
            break;
        }
    }

    body.innerHTML = "";
    for (var i = first; i < first + 12; i++) {
        // Limit index
        if (i >= sch.length) { break; }

        var start = sch[i][0];
        var end = sch[i][1];
        var row = body.insertRow();

        // Add cells to row
        row.insertCell().innerHTML = `${sch[i][0].substr(0, 2)}:${sch[i][0].substr(2, 2)}:${sch[i][0].substr(4, 2)}`;
        row.insertCell().innerHTML = `${sch[i][1].substr(0, 2)}:${sch[i][1].substr(2, 2)}:${sch[i][1].substr(4, 2)}`;
        row.insertCell().innerHTML = sch[i][2];
        row.insertCell().innerHTML = sch[i][3];

        // Set past entries as disabled (except last entry)
        if (time > start && i != sch.length - 1) {
            row.removeAttribute("active", "");
            row.setAttribute("disabled", "");
        }

        // Set current entry as active
        if (time > start && time < end) {
            row.removeAttribute("disabled", "");
            row.setAttribute("active", "");
        }
    }
}


/**
 * Update progress block
 * @param element Block body element
 */
function block_progress(element)
{
    var progressList = document.getElementById("progress-list");
    var progressStatus = document.getElementById("progress-status");
    
    // Check if there are active downloads
    if (Object.keys(current_progress).length === 0) {
        progressStatus.textContent = "No active downloads";
        progressList.innerHTML = "";
        return;
    }
    
    progressStatus.textContent = `${Object.keys(current_progress).length} active download(s)`;
    progressList.innerHTML = "";
    
    // Create progress items for each active download
    for (var productKey in current_progress) {
        var progress = current_progress[productKey];
        
        var progressItem = document.createElement("div");
        progressItem.className = "progress-item";
        
        var title = document.createElement("h4");
        title.textContent = `${progress.product_type}: ${progress.product_name}`;
        progressItem.appendChild(title);
        
        var progressBar = document.createElement("div");
        progressBar.className = "progress-bar";
        var progressFill = document.createElement("div");
        progressFill.className = "progress-fill";
        progressFill.style.width = `${Math.min(100, progress.progress_percent)}%`;
        progressBar.appendChild(progressFill);
        progressItem.appendChild(progressBar);
        
        var progressText = document.createElement("div");
        progressText.className = "progress-segments";
        progressText.textContent = `${progress.segments_received}/${progress.total_segments} segments (${Math.round(progress.progress_percent)}%)`;
        progressItem.appendChild(progressText);
        
        // Add channel information
        for (var channel in progress.channels) {
            var channelInfo = document.createElement("div");
            channelInfo.className = "progress-channel";
            var channelData = progress.channels[channel];
            channelInfo.textContent = `${channel}: ${channelData.segment_count} segments [${channelData.segments.join(', ')}]`;
            progressItem.appendChild(channelInfo);
        }
        
        progressList.appendChild(progressItem);
    }
}

/**
 * Load available pre-rendered timelapses
 */
function loadTimelapses() {
    // Use the existing file serving mechanism instead of custom API endpoints
    const timelapseFiles = [
        { name: '3h MP4', api: '/api/timelapses/latest_3h_mp4.mp4', hours: 3, format: 'MP4' },
        { name: '24h MP4', api: '/api/timelapses/latest_24h_mp4.mp4', hours: 24, format: 'MP4' },
        { name: '3h GIF', api: '/api/timelapses/latest_3h_gif.gif', hours: 3, format: 'GIF' },
        { name: '24h GIF', api: '/api/timelapses/latest_24h_gif.gif', hours: 24, format: 'GIF' }
    ];
    
    const statusElement = document.getElementById('timelapse-status');
    let statusHTML = '<div style="font-size: 12px; margin-bottom: 8px; color: #4CAF50;">📽️ Available Downloads:</div>';
    let availableCount = 0;
    let processedCount = 0;
    
    // Check each timelapse file availability
    timelapseFiles.forEach((tl) => {
        fetch(tl.api, { method: 'HEAD' })
            .then(response => {
                if (response.ok) {
                    availableCount++;
                    statusHTML += `<div style="margin: 3px 0; padding: 2px 5px; background: rgba(76, 175, 80, 0.1); border-radius: 3px;">`;
                    statusHTML += `<a href="${tl.api}" download style="color: #4CAF50; text-decoration: none; font-size: 11px;">`;
                    statusHTML += `📥 ${tl.name}</a> `;
                    statusHTML += `<span style="color: #888; font-size: 9px; margin-left: 5px;">✓ Ready</span>`;
                    statusHTML += `</div>`;
                } else {
                    statusHTML += `<div style="margin: 3px 0; padding: 2px 5px; background: rgba(128, 128, 128, 0.1); border-radius: 3px;">`;
                    statusHTML += `<span style="color: #888; text-decoration: none; font-size: 11px;">`;
                    statusHTML += `⏳ ${tl.name}</span> `;
                    statusHTML += `<span style="color: #666; font-size: 9px; margin-left: 5px;">Generating...</span>`;
                    statusHTML += `</div>`;
                }
                
                processedCount++;
                // Update status after checking all files
                if (processedCount === timelapseFiles.length) {
                    if (availableCount === 0) {
                        statusHTML = '<div style="color: #888; font-size: 11px;">⏳ Timelapses are being generated...</div>' +
                                   '<div style="color: #666; font-size: 10px; margin-top: 5px;">Check back in a few minutes</div>';
                    }
                    statusElement.innerHTML = statusHTML;
                }
            })
            .catch(error => {
                console.error(`Error checking ${tl.name}:`, error);
                statusHTML += `<div style="margin: 3px 0; color: #f44336; font-size: 11px;">❌ ${tl.name} - Error</div>`;
                
                processedCount++;
                if (processedCount === timelapseFiles.length) {
                    statusElement.innerHTML = statusHTML;
                }
            });
    });
}

/**
 * Check file age and availability
 */
function checkFileAge(filename) {
    // This could be enhanced to show file age/availability via API
    console.log(`Checking ${filename} availability...`);
}

/**
 * Refresh timelapse list
 */
function refreshTimelapses() {
    const statusElement = document.getElementById('timelapse-status');
    statusElement.innerHTML = '<span style="color: #FFA500;">Refreshing...</span>';
    
    // Reload both the list and latest timelapse
    setTimeout(() => {
        loadTimelapses();
        loadLatestTimelapse();
    }, 1000);
}

/**
 * Create timelapse video or GIF (now just refreshes the list)
 */
function createTimelapse(hours, type, format) {
    const statusElement = document.getElementById('timelapse-status');
    
    statusElement.innerHTML = `<span style="color: #4CAF50;">Timelapses are generated automatically every hour!</span><br>` +
                             `<span style="color: #CCC; font-size: 11px;">Check back in a few minutes for updated ${hours}h ${format.toUpperCase()} timelapse.</span>`;
    
    // Refresh the list after a moment
    setTimeout(() => {
        loadTimelapses();
    }, 3000);
}

/**
 * Load latest 3hr timelapse for display
 */
function loadLatestTimelapse() {
    const statusElement = document.getElementById('latest-timelapse-status');
    const videoElement = document.getElementById('latest-timelapse-video');
    
    // Try to load 3hr MP4 timelapse using existing file serving mechanism
    const timelapseUrl = '/api/timelapses/latest_3h_mp4.mp4';
    
    // Test if the file exists
    fetch(timelapseUrl, { method: 'HEAD' })
        .then(response => {
            if (response.ok) {
                statusElement.style.display = 'none';
                videoElement.src = timelapseUrl;
                videoElement.style.display = 'block';
                videoElement.title = 'Latest 3-hour timelapse (MP4)';
            } else {
                statusElement.textContent = 'No 3hr timelapse available yet';
                statusElement.style.color = '#888';
                videoElement.style.display = 'none';
            }
        })
        .catch(error => {
            console.error('Error loading latest timelapse:', error);
            statusElement.textContent = 'Error loading timelapse';
            statusElement.style.color = '#f44336';
            videoElement.style.display = 'none';
        });
}

/**
 * Show timelapse information
 */
function showTimelapseInfo() {
    const statusElement = document.getElementById('timelapse-status');
    statusElement.innerHTML = `
        <div style="color: #4CAF50; font-size: 12px; margin-bottom: 5px;">📊 Timelapse Information</div>
        <div style="font-size: 11px; color: #CCC; line-height: 1.4;">
            • Generated automatically every 30 minutes<br>
            • 3-hour timelapses: ~18 images from last 3 hours<br>
            • 24-hour timelapses: ~144 images from last 24 hours<br>
            • Available in MP4 (video) and GIF (animated) formats<br>
            • GK-2A satellite transmits every 10 minutes<br>
        </div>
        <div style="margin-top: 8px; font-size: 10px; color: #888;">
            API: /api/timelapse/fd/{duration}/{type}
        </div>
    `;
    
    // Refresh the list after showing info
    setTimeout(() => {
        loadTimelapses();
    }, 5000);
}

/**
 * Tab Management Functions
 */
function openTab(evt, tabName) {
    var i, tabcontent, tablinks;
    
    // Hide all tab content
    tabcontent = document.getElementsByClassName("tab-content");
    for (i = 0; i < tabcontent.length; i++) {
        tabcontent[i].classList.remove("active");
    }
    
    // Remove active class from all tab buttons
    tablinks = document.getElementsByClassName("tab-button");
    for (i = 0; i < tablinks.length; i++) {
        tablinks[i].classList.remove("active");
    }
    
    // Show the selected tab and mark button as active
    document.getElementById(tabName).classList.add("active");
    evt.currentTarget.classList.add("active");
    
    // Load images when Images tab is opened
    if (tabName === 'tab-images') {
        loadAllImages();
    }
}

/**
 * Latest Images Management
 */
var imageTypes = {
    'FD': 'Full Disk - Complete Earth hemisphere imagery',
    'SICEF24': 'Sea Ice Concentration Forecast (24h)',
    'SICEF48': 'Sea Ice Concentration Forecast (48h)', 
    'SSTF24': 'Sea Surface Temperature Forecast (24h)',
    'SSTF48': 'Sea Surface Temperature Forecast (48h)',
    'SSTF72': 'Sea Surface Temperature Forecast (72h)',
    'SSTA': 'Sea Surface Temperature Analysis',
    'COMSFOG': 'Communications Fog Analysis',
    'COMSIR1': 'Communications Infrared Channel 1',
    'FCT': 'Forecast Data Products',
    'FOGVIS': 'Fog Visibility Analysis',
    'GWW3F': 'Global Wave Watch III Forecast',
    'RWW3A': 'Regional Wave Watch III Analysis',
    'RWW3F': 'Regional Wave Watch III Forecast',
    'RWW3M': 'Regional Wave Watch III Model',
    'SUFA03': 'Surface Analysis (3h intervals)',
    'SUFA12': 'Surface Analysis (12h intervals)', 
    'SUFF24': 'Surface Forecast (24h)',
    'UP50A': 'Upper Level Analysis (50hPa)',
    'UP50F24': 'Upper Level Forecast (50hPa, 24h)',
    'UP50F48': 'Upper Level Forecast (50hPa, 48h)',
    'ANT': 'Alpha-Numeric Text (schedules)',
    'ADD': 'Additional Data Products'
};

var imageSizeMode = 'normal'; // 'normal' or 'large'

function loadAllImages() {
    const grid = document.getElementById('images-grid');
    grid.innerHTML = '<div class="loading-grid">Loading latest images...</div>';
    
    const imageKeys = Object.keys(imageTypes);
    let loadedCount = 0;
    let imageData = {};
    
    // Load metadata for each image type
    imageKeys.forEach(type => {
        http_get(`/api/latest/${type.toLowerCase()}`, (res) => {
            if (res.status == 200) {
                res.json().then((data) => {
                    imageData[type] = data;
                    console.log(`Loaded data for ${type}:`, data); // Debug log
                }).catch(err => {
                    console.error(`JSON parse error for ${type}:`, err);
                    imageData[type] = null;
                }).finally(() => {
                    loadedCount++;
                    if (loadedCount === imageKeys.length) {
                        renderImageGrid(imageData);
                    }
                });
            } else {
                console.log(`No data for ${type}, status: ${res.status}`); // Debug log
                imageData[type] = null;
                loadedCount++;
                if (loadedCount === imageKeys.length) {
                    renderImageGrid(imageData);
                }
            }
        });
    });
}

function renderImageGrid(imageData) {
    const grid = document.getElementById('images-grid');
    grid.className = `images-grid ${imageSizeMode}`;
    
    let html = '';
    
    Object.keys(imageTypes).forEach(type => {
        const data = imageData[type];
        const description = imageTypes[type];
        
        html += `
            <div class="image-card">
                <div class="image-header">
                    <div class="image-type">${type}</div>
                    <div class="image-description">${description}</div>
                </div>
        `;
        
        if (data && data.image) {
            const imageUrl = `/api/latest/${type.toLowerCase()}/image`;
            const partialUrl = `/api/latest/${type.toLowerCase()}/partial`;
            
            html += `
                <img class="image-preview" src="${imageUrl}" alt="${type}" 
                     onclick="window.open('${imageUrl}', '_blank')" 
                     onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                <div class="no-image" style="display: none;">Image load failed</div>
                
                <div class="image-info">
                    <div class="info-row">
                        <span class="label">Timestamp:</span>
                        <span class="value">${formatTimestamp(data.timestamp)}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">File Size:</span>
                        <span class="value">${formatFileSize(data.size || 0)}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Channel:</span>
                        <span class="value">${data.channel !== null ? data.channel : 'N/A'}</span>
                    </div>
                    <div class="info-row">
                        <span class="label">Hash:</span>
                        <span class="value" title="${data.hash || ''}">${(data.hash || '').substring(0, 16)}...</span>
                    </div>
                </div>
                
                <div class="image-actions">
                    <a href="${imageUrl}" target="_blank" class="action-btn">📷 Full Size</a>
                    <a href="${partialUrl}" target="_blank" class="action-btn partial">⚡ Partial</a>
                    <button onclick="copyImageUrl('${imageUrl}')" class="action-btn">📋 Copy URL</button>
                </div>
            `;
        } else {
            html += `
                <div class="no-image">No recent ${type} image available</div>
                <div class="image-info">
                    <div class="info-row">
                        <span class="label">Status:</span>
                        <span class="value">No data received</span>
                    </div>
                </div>
                <div class="image-actions">
                    <button class="action-btn" disabled>No image available</button>
                </div>
            `;
        }
        
        html += '</div>';
    });
    
    grid.innerHTML = html;
}

function refreshAllImages() {
    loadAllImages();
}

function toggleImageSizes() {
    imageSizeMode = imageSizeMode === 'normal' ? 'large' : 'normal';
    const grid = document.getElementById('images-grid');
    grid.className = `images-grid ${imageSizeMode}`;
    
    // Update button text
    const btn = document.querySelector('.size-btn');
    btn.textContent = imageSizeMode === 'large' ? '📏 Normal Size' : '📏 Large Size';
}

function copyImageUrl(url) {
    const fullUrl = window.location.origin + url;
    navigator.clipboard.writeText(fullUrl).then(() => {
        // Show temporary feedback
        const btn = event.target;
        const originalText = btn.textContent;
        btn.textContent = '✅ Copied!';
        setTimeout(() => {
            btn.textContent = originalText;
        }, 2000);
    }).catch(() => {
        // Fallback for older browsers
        prompt('Copy this URL:', fullUrl);
    });
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatTimestamp(timestamp) {
    if (!timestamp) return 'Unknown';
    
    try {
        // Remove the 'Z' suffix and parse as local time
        const date = new Date(timestamp.replace('Z', ''));
        
        // Format as DD/MM/YYYY HH:MM:SS
        const day = date.getDate().toString().padStart(2, '0');
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const year = date.getFullYear();
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        const seconds = date.getSeconds().toString().padStart(2, '0');
        
        return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
    } catch (e) {
        return 'Invalid date';
    }
}
