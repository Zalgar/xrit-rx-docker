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
