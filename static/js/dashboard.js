// Dashboard JavaScript

$(document).ready(function() {
    // Initialize DataTables on customer rankings table
    if ($('#customerRankingsTable').length) {
        var startDate = $('#customerRankingsTable').data('start-date');
        var endDate = $('#customerRankingsTable').data('end-date');
        var btsPeriod = $('#customerRankingsTable').data('bts-period');

        $('#customerRankingsTable').DataTable({
            dom: '<"row"<"col-sm-12 col-md-4"B><"col-sm-12 col-md-4"l><"col-sm-12 col-md-4"f>>' +
                 '<"row"<"col-sm-12"tr>>' +
                 '<"row"<"col-sm-12 col-md-5"i><"col-sm-12 col-md-7"p>>',
            buttons: [
                {
                    extend: 'csv',
                    className: 'btn btn-sm btn-success',
                    text: '<i class="fas fa-file-csv me-1"></i> CSV',
                    filename: 'Customer_Rankings_' + startDate + '_to_' + endDate
                },
                {
                    extend: 'excel',
                    className: 'btn btn-sm btn-success',
                    text: '<i class="fas fa-file-excel me-1"></i> Excel',
                    filename: 'Customer_Rankings_' + startDate + '_to_' + endDate,
                    title: 'Customer Rankings - Stock vs BTS Sales',
                    messageTop: 'Period: ' + btsPeriod
                },
                {
                    extend: 'pdf',
                    className: 'btn btn-sm btn-danger',
                    text: '<i class="fas fa-file-pdf me-1"></i> PDF',
                    filename: 'Customer_Rankings_' + startDate + '_to_' + endDate,
                    title: 'Customer Rankings - Stock vs BTS Sales',
                    messageTop: 'Analysis Period: ' + btsPeriod,
                    orientation: 'landscape',
                    pageSize: 'A4',
                    customize: function(doc) {
                        doc.styles.tableHeader.fillColor = '#2c3e50';
                        doc.styles.tableHeader.color = 'white';
                    }
                },
                {
                    extend: 'print',
                    className: 'btn btn-sm btn-secondary',
                    text: '<i class="fas fa-print me-1"></i> Print',
                    title: 'Customer Rankings - Stock vs BTS Sales',
                    messageTop: '<h4>Analysis Period: ' + btsPeriod + '</h4>',
                    customize: function(win) {
                        $(win.document.body).css('font-size', '10pt');
                        $(win.document.body).find('table').addClass('compact').css('font-size', 'inherit');
                    }
                }
            ],
            order: [[4, 'desc']], // Sort by ratio (column index 4) descending
            pageLength: 10, // Show 10 rows per page by default
            lengthMenu: [[10, 20, 25, 50, 100, -1], [10, 20, 25, 50, 100, "All"]],
            language: {
                search: "Search customers:",
                lengthMenu: "Show _MENU_ customers per page",
                info: "Showing _START_ to _END_ of _TOTAL_ customers",
                infoEmpty: "No customers found",
                infoFiltered: "(filtered from _MAX_ total customers)",
                zeroRecords: "No matching customers found",
                paginate: {
                    first: "First",
                    last: "Last",
                    next: "Next",
                    previous: "Previous"
                }
            },
            columnDefs: [
                { orderable: false, targets: 0 }, // Disable sorting on # column
                { className: "text-end", targets: [2, 3, 4] }, // Right align numeric columns
                { className: "text-center", targets: [5] } // Center align risk band
            ],
            drawCallback: function() {
                // Re-apply row colors after each draw
                $('#customerRankingsTable tbody tr').each(function() {
                    if ($(this).find('.status-badge').hasClass('critical')) {
                        $(this).addClass('critical');
                    } else if ($(this).find('.status-badge').hasClass('warning')) {
                        $(this).addClass('warning');
                    } else if ($(this).find('.status-badge').hasClass('healthy')) {
                        $(this).addClass('healthy');
                    }
                });
            }
        });
    }

    // Initialize DataTables on product rankings table
    if ($('#productRankingsTable').length) {
        var startDate = $('#productRankingsTable').data('start-date');
        var endDate = $('#productRankingsTable').data('end-date');
        var btsPeriod = $('#productRankingsTable').data('bts-period');

        $('#productRankingsTable').DataTable({
            dom: '<"row"<"col-sm-12 col-md-4"B><"col-sm-12 col-md-4"l><"col-sm-12 col-md-4"f>>' +
                 '<"row"<"col-sm-12"tr>>' +
                 '<"row"<"col-sm-12 col-md-5"i><"col-sm-12 col-md-7"p>>',
            buttons: [
                {
                    extend: 'csv',
                    className: 'btn btn-sm btn-success',
                    text: '<i class="fas fa-file-csv me-1"></i> CSV',
                    filename: 'Product_Rankings_' + startDate + '_to_' + endDate
                },
                {
                    extend: 'excel',
                    className: 'btn btn-sm btn-success',
                    text: '<i class="fas fa-file-excel me-1"></i> Excel',
                    filename: 'Product_Rankings_' + startDate + '_to_' + endDate,
                    title: 'Product Rankings - Stock vs BTS Sales',
                    messageTop: 'Period: ' + btsPeriod
                },
                {
                    extend: 'pdf',
                    className: 'btn btn-sm btn-danger',
                    text: '<i class="fas fa-file-pdf me-1"></i> PDF',
                    filename: 'Product_Rankings_' + startDate + '_to_' + endDate,
                    title: 'Product Rankings - Stock vs BTS Sales',
                    messageTop: 'Analysis Period: ' + btsPeriod,
                    orientation: 'landscape',
                    pageSize: 'A4',
                    customize: function(doc) {
                        doc.styles.tableHeader.fillColor = '#2c3e50';
                        doc.styles.tableHeader.color = 'white';
                    }
                },
                {
                    extend: 'print',
                    className: 'btn btn-sm btn-secondary',
                    text: '<i class="fas fa-print me-1"></i> Print',
                    title: 'Product Rankings - Stock vs BTS Sales',
                    messageTop: '<h4>Analysis Period: ' + btsPeriod + '</h4>',
                    customize: function(win) {
                        $(win.document.body).css('font-size', '10pt');
                        $(win.document.body).find('table').addClass('compact').css('font-size', 'inherit');
                    }
                }
            ],
            order: [[6, 'desc']], // Sort by ratio (column index 6) descending
            pageLength: 10, // Show 10 rows per page by default
            lengthMenu: [[10, 20, 25, 50, 100, -1], [10, 20, 25, 50, 100, "All"]],
            language: {
                search: "Search products:",
                lengthMenu: "Show _MENU_ products per page",
                info: "Showing _START_ to _END_ of _TOTAL_ products",
                infoEmpty: "No products found",
                infoFiltered: "(filtered from _MAX_ total products)",
                zeroRecords: "No matching products found",
                paginate: {
                    first: "First",
                    last: "Last",
                    next: "Next",
                    previous: "Previous"
                }
            },
            columnDefs: [
                { orderable: false, className: "text-center", targets: 0 }, // Disable sorting and center align # column
                { className: "text-start", targets: [1, 2, 3] }, // Left align text columns (School, Style Code, Product Name)
                { className: "text-end", targets: [4, 5, 6] }, // Right align numeric columns (Stock Value, BTS Sales, Ratio)
                { className: "text-center", targets: [7] } // Center align risk band
            ],
            drawCallback: function() {
                // Re-apply row colors after each draw
                $('#productRankingsTable tbody tr').each(function() {
                    if ($(this).find('.status-badge').hasClass('critical')) {
                        $(this).addClass('critical');
                    } else if ($(this).find('.status-badge').hasClass('warning')) {
                        $(this).addClass('warning');
                    } else if ($(this).find('.status-badge').hasClass('healthy')) {
                        $(this).addClass('healthy');
                    }
                });
            }
        });
    }

    // Initialize Heatmap
    function renderHeatmap(data) {
        const container = document.getElementById('heatmapContainer');
        if (!container || !data || !data.schools || data.schools.length === 0) {
            return;
        }

        const schools = data.schools;
        const products = data.products;
        const ratios = data.data;
        const stockData = data.stock_data;
        const salesData = data.sales_data;

        // Build heatmap table
        let html = '<table class="heatmap-table">';

        // Header row
        html += '<thead><tr>';
        html += '<th class="school-header">School</th>';
        for (let p = 0; p < products.length; p++) {
            html += `<th title="${products[p]}">${products[p]}</th>`;
        }
        html += '</tr></thead>';

        // Data rows
        html += '<tbody>';
        for (let s = 0; s < schools.length; s++) {
            html += '<tr>';
            html += `<td class="school-name">${schools[s]}</td>`;

            for (let p = 0; p < products.length; p++) {
                const ratio = ratios[s][p];
                const stock = stockData[s][p];
                const sales = salesData[s][p];

                // Determine color class
                let colorClass = 'heatmap-no-data';
                let displayValue = '-';

                if (ratio === 0 && stock === 0 && sales === 0) {
                    colorClass = 'heatmap-no-data';
                    displayValue = '-';
                } else if (ratio >= 999999) {
                    colorClass = 'heatmap-critical';
                    displayValue = '∞';
                } else if (ratio > 3) {
                    colorClass = 'heatmap-critical';
                    displayValue = ratio.toFixed(1);
                } else if (ratio > 2) {
                    colorClass = 'heatmap-warning';
                    displayValue = ratio.toFixed(1);
                } else if (ratio > 0) {
                    colorClass = 'heatmap-healthy';
                    displayValue = ratio.toFixed(1);
                }

                const tooltip = `School: ${schools[s]}\\nProduct: ${products[p]}\\nStock: $${stock.toFixed(2)}\\nSales: $${sales.toFixed(2)}\\nRatio: ${displayValue}x`;

                html += `<td title="${tooltip}">`;
                html += `<div class="heatmap-cell ${colorClass}">`;
                html += `<span class="heatmap-cell-value">${displayValue}</span>`;
                html += `</div>`;
                html += `</td>`;
            }

            html += '</tr>';
        }
        html += '</tbody>';
        html += '</table>';

        container.innerHTML = html;
    }

    // Get heatmap data from context and render
    const heatmapDataElement = document.getElementById('heatmapContainer');
    if (heatmapDataElement && window.heatmapData) {
        renderHeatmap(window.heatmapData);
    }
});
