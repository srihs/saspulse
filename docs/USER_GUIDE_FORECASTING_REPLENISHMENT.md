# SasPulse User Guide: Forecasting & Replenishment

> **For Non-Technical Users**
> This guide explains how to use the Forecasting and Replenishment features in simple, everyday language.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Forecasting Section](#forecasting-section)
   - [BTS Sales Forecasting](#bts-sales-forecasting)
3. [Replenishment Section](#replenishment-section)
   - [Store Replenishment (Store Manager View)](#store-replenishment-store-manager-view)
   - [Store Replenishment Requests](#store-replenishment-requests)
   - [DP Team Replenishment (Demand Planning View)](#dp-team-replenishment-demand-planning-view)

---

## Introduction

**What is Forecasting?**
Forecasting is like looking into a crystal ball to predict how much of each product you'll sell in the future. This helps you order the right amount of stock - not too much (which wastes money and space) and not too little (which means you might run out and disappoint customers).

**What is Replenishment?**
Replenishment is the process of ordering more stock when you're running low. Think of it like restocking your kitchen pantry - when you notice you're running out of flour, you add it to your shopping list.

**Who uses these features?**
- **Store Managers:** Request stock for their locations
- **Demand Planning (DP) Team:** Review and approve stock requests, manage overall inventory

---

## Forecasting Section

### BTS Sales Forecasting

**Menu Location:** Dashboard → BTS Sales Forecasting

**What does it do?**
This page predicts how much of each product you'll need for the Back-to-School (BTS) season. It looks at your past sales and calculates expected sales for each month.

---

#### 📊 Understanding the Page

**Top Section: Forecast Summary Cards**

When you first open the page, you'll see colored cards at the top:

1. **Total Schools (Blue Card)**
   - Shows how many schools/customers are in your forecast
   - Example: "25 Schools" means 25 different customers

2. **Total Products (Green Card)**
   - Shows how many different products you're forecasting
   - Example: "150 Products" means 150 different items

3. **Total Forecasted Sales (Purple Card)**
   - Shows the total dollar amount expected in sales
   - Example: "$450,000" means you're expected to sell this much

4. **Average Monthly Sales (Orange Card)**
   - Shows average sales per month
   - Example: "$37,500/month" is your average

---

#### 🔍 Filters Section

**Purpose:** Narrow down what you want to see

**Available Filters:**

1. **School/Customer Filter**
   - Dropdown menu showing all your customers
   - Select "All Customers" to see everything
   - Select a specific school to see only that customer's forecast

2. **Category Filter**
   - Dropdown showing product categories (e.g., "Girls Shop", "Boys Shop")
   - Select "All Categories" to see everything
   - Select specific category to focus on one product line

3. **Apply Filters Button**
   - Click this blue button after selecting your filters
   - The page will refresh and show only what you selected

---

#### 📋 Main Forecast Table

**What you'll see:**

The table shows each product with predicted sales for every month. Here's what each column means:

**Fixed Columns (Always Visible):**
- **Customer:** The school or customer name
- **Product:** The product name
- **Style Code:** Internal product code
- **SKU:** Unique product identifier (like a barcode)

**Monthly Columns (Scroll to see all):**
- **January, February, March... December**
- Each shows predicted quantity to sell that month
- Example: "25" means you're expected to sell 25 units

**How to Use the Table:**

1. **Search Box (top right):**
   - Type any word to find specific products
   - Example: Type "shirt" to find all shirts

2. **Sort Columns:**
   - Click any column header to sort
   - Click again to reverse the sort order

3. **Export Buttons (top left):**
   - **Excel Button:** Download the forecast as an Excel spreadsheet
   - **CSV Button:** Download as a CSV file (opens in Excel)
   - **PDF Button:** Download as a PDF document
   - **Print Button:** Print the forecast directly

4. **Rows Per Page:**
   - Bottom of table shows "Show 25 entries"
   - Change this to see more/fewer rows at once

5. **Page Navigation:**
   - Bottom right has "Previous" and "Next" buttons
   - Use these to see more products if you have many

---

#### 💡 How to Use This Information

**For Store Managers:**
- Look at upcoming months to see what products you'll need
- Compare to your current stock levels
- Request replenishment for products where forecast > current stock

**For Demand Planning Team:**
- Review forecasts before approving store requests
- Plan purchasing and supplier orders
- Allocate inventory across stores based on forecasts

**Example Scenario:**
> You see Product "Boys Shirt - Blue" has forecast:
> - January: 10 units
> - February: 50 units (BTS season starts)
> - March: 45 units
>
> Your current stock: 20 units
>
> **Action:** You need to order more! (10+50+45 = 105 needed, only have 20)

---

## Replenishment Section

The replenishment process has **two levels of approval**:
1. **Store Manager** creates and approves requests
2. **DP Team** reviews and gives final approval

---

### Store Replenishment (Store Manager View)

**Menu Location:** Dashboard → Replenishment → Store Replenishment

**What does it do?**
This page helps store managers identify products that are running low and request more stock.

---

#### 📊 Understanding the Page

**Shortage Summary Card (Top)**

Shows a quick overview of your stock situation:
- **Total Products:** How many different products you sell
- **Low Stock Items:** Products running low (highlighted in orange/red)
- **Critical Stockouts:** Products you're almost out of (urgent!)

---

#### 📋 Stock Shortage Table

**What you'll see:**

A table showing all your products with their current stock levels and whether you need more.

**Columns Explained:**

1. **Customer**
   - Your school or location name
   - Products are grouped by customer

2. **Product Name**
   - The name of the item
   - Example: "Girls Winter Jacket - Navy"

3. **Style Code**
   - Internal product code
   - Used for ordering and tracking

4. **SKU**
   - Unique identifier for the exact product variant
   - Like a barcode number

5. **Current Stock**
   - How many units you have right now
   - **Color Coding:**
     - 🟢 Green: Good stock level
     - 🟡 Yellow: Getting low (10-30 days left)
     - 🔴 Red: Critical (less than 10 days left)

6. **Forecasted Demand**
   - How many units you're expected to sell soon
   - Based on past sales patterns

7. **Stock Shortage**
   - The difference between what you have and what you need
   - **Negative number = You need this many more**
   - Example: "-25" means you need to order 25 units

8. **Status**
   - Shows current request status:
     - ⚪ **Available:** Not yet added to a request
     - 🟡 **Pending Store Approval:** In your request, waiting for you to approve
     - 🟢 **Store Approved:** You approved it, sent to DP Team
     - 🔵 **DP Approved:** Final approval, order will be placed

9. **Actions**
   - Buttons to take action on each product

---

#### ⚙️ Action Buttons Explained

For each product, you have two buttons:

**1. "Approve" Button (Green)**
- **When to use:** Product needs restocking at the suggested quantity
- **What happens:**
  - Product is added to your replenishment request
  - Uses the "Stock Shortage" amount automatically
  - Status changes to "Pending Store Approval"
  - Row becomes grayed out (can't add again)

**Example:**
> Product: "Boys Shirt - Blue"
> Current Stock: 10
> Forecasted Demand: 50
> Stock Shortage: -40
>
> **Click "Approve"** → Request for 40 units created

**2. "Modify" Button (Blue)**
- **When to use:** You want to order a different quantity than suggested
- **What happens:**
  - A popup window appears
  - You can enter your custom quantity
  - Example: Suggestion is 40 units, but you want to order 50
  - Product added to request with YOUR quantity

**Example:**
> Product: "Boys Shirt - Blue"
> Stock Shortage suggests: -40 units
> But you know a big event is coming...
>
> **Click "Modify"** → Type "60" → Product added with 60 units

---

#### 🔍 Table Features

**Search Box (Top Right):**
- Type to find specific products
- Searches across all columns
- Example: Type "jacket" to see all jackets

**Export Buttons (Top Left):**
- Download your stock shortage report
- Use Excel to analyze or share with your team

**Filters:**
- Use dropdowns to show only specific categories or customers

---

#### ⚠️ Important Things to Know

**Grayed Out Rows:**
- Products already in a pending request
- You can't add them again until request is processed
- This prevents duplicate orders

**Stock Shortage Calculation:**
- Automatically calculated based on forecast and current stock
- Always shows as a **negative number** when you need more
- Example: -25 means "need 25 more units"

**Color Indicators:**
- 🔴 Red = Urgent (less than 10 days of stock)
- 🟡 Yellow = Warning (10-30 days of stock)
- 🟢 Green = Healthy (30+ days of stock)

---

### Store Replenishment Requests

**Menu Location:** Dashboard → Replenishment → Store Replenishment Requests

**What does it do?**
This page shows all the replenishment requests you've created. Think of it like your "shopping cart" for stock orders.

---

#### 📊 Understanding the Page

**Request Summary Cards (Top)**

Shows statistics about your requests:

1. **Total Requests**
   - How many replenishment batches you've created
   - Each batch can contain multiple products

2. **Pending Store Approval**
   - Requests waiting for YOU to review and approve
   - Action needed!

3. **Store Approved**
   - Requests you approved, now with DP Team
   - Waiting for their final approval

4. **DP Approved**
   - Requests that received final approval
   - Order will be or has been placed

---

#### 📋 Requests Table

**What you'll see:**

A list of all your replenishment request batches:

**Columns Explained:**

1. **Request #**
   - Unique identifier for each request batch
   - Example: "REQ-2024-001"
   - Click this number to see full details

2. **Created Date**
   - When you created this request
   - Format: "Jan 15, 2024 10:30 AM"

3. **Total Items**
   - How many different products in this request
   - Example: "12 items" means 12 different products

4. **Total Units**
   - Total quantity across all products
   - Example: "450 units" total to order

5. **Store Status**
   - YOUR approval status:
     - 🟡 **Pending:** You haven't approved yet
     - 🟢 **Approved:** You approved it

6. **DP Status**
   - Demand Planning Team's status:
     - ⏳ **Pending Review:** They haven't reviewed yet
     - 🟢 **Approved:** They approved it
     - 🔴 **Rejected:** They rejected it (with reason)

7. **Actions**
   - Buttons to view or manage the request

---

#### 🔍 Request Details Page

**When you click a Request #:**

You'll see a detailed page showing:

**Request Header:**
- Request number
- Creation date
- Overall status

**Products Table:**

For each product in the request:

1. **Product Information**
   - Customer name
   - Product name
   - Style code and SKU

2. **Quantities**
   - Current stock
   - Requested quantity
   - How the request will be fulfilled

3. **Status**
   - Current approval status
   - Who approved and when

**Approval Buttons (if pending):**

- **"Approve All" Button (Green)**
  - Approves all products in this request at once
  - Sends to DP Team for final review

- **"Approve Selected" Button (Blue)**
  - Check boxes next to specific products
  - Only approve those you selected
  - Use this if you want to approve some but not all

---

#### 💡 How to Use This Page

**Daily Workflow:**

1. **Check "Pending Store Approval" count**
   - If it shows a number, you have requests waiting

2. **Click on pending request numbers**
   - Review the products and quantities

3. **Verify quantities are correct**
   - Make sure you actually need these amounts
   - Check against your current stock

4. **Click "Approve All"**
   - If everything looks good
   - Request moves to DP Team

5. **Monitor DP Status**
   - Check back to see if DP Team approved
   - If rejected, read the reason and create new request

**Example Scenario:**
> You have Request #REQ-2024-045 with 15 products.
>
> **Step 1:** Click "REQ-2024-045" to open details
> **Step 2:** Review the list - all quantities look good
> **Step 3:** Click "Approve All" button at the top
> **Step 4:** Status changes to "Store Approved, Pending DP Review"
> **Step 5:** Come back tomorrow to check if DP approved

---

### DP Team Replenishment (Demand Planning View)

**Menu Location:** Dashboard → Replenishment → DP Team Replenishment

**What does it do?**
This is where the Demand Planning Team reviews requests from all stores and gives final approval before orders are placed with suppliers.

---

#### 📊 Understanding the Page

**DP Team Summary Cards (Top)**

Shows statistics across ALL stores:

1. **Total Pending Requests**
   - How many store requests need your review
   - This is your workload

2. **Total Items Pending**
   - Total number of different products across all requests
   - Shows scale of review needed

3. **Total Units Pending**
   - Total quantity requested across all stores
   - Example: "2,500 units" need approval

4. **Stores with Requests**
   - How many different locations submitted requests
   - Shows demand across your network

---

#### 📋 Store Requests Table

**What you'll see:**

A list of all replenishment requests from all stores, grouped by store:

**Columns Explained:**

1. **Store/Customer**
   - Which store or location submitted the request
   - Products are grouped by store

2. **Product Name**
   - The item being requested
   - Full product description

3. **Style Code & SKU**
   - Product identifiers for ordering

4. **Current Stock (at that store)**
   - How many units the store currently has
   - Helps you verify they really need more

5. **Requested Quantity**
   - How many units the store wants
   - This is what you're approving or rejecting

6. **Forecasted Demand**
   - Expected sales for this product
   - Use this to verify the requested quantity makes sense

7. **Store Approval Status**
   - Shows if the store manager already approved
   - Should be "Store Approved" if it reached you

8. **Your Status (DP Status)**
   - Your approval decision:
     - ⏳ **Pending:** You haven't reviewed yet
     - 🟢 **Approved:** You approved it
     - 🔴 **Rejected:** You rejected it

9. **Actions**
   - Buttons to approve or reject

---

#### ⚙️ DP Team Action Buttons

**For each request, you have two options:**

**1. "Approve" Button (Green)**
- **When to use:**
  - Requested quantity matches forecast
  - Store has legitimate need
  - Inventory is available or can be ordered

- **What happens:**
  - Product is approved for ordering
  - Store will receive notification
  - Purchasing can proceed
  - Status changes to "DP Approved"

**2. "Reject" Button (Red)**
- **When to use:**
  - Requested quantity is too high
  - Inventory constraints
  - Budget limitations
  - Forecast doesn't support the quantity

- **What happens:**
  - Popup asks for rejection reason
  - You type why you're rejecting
  - Store manager gets notification with reason
  - They can submit a new request if needed

---

#### 🧐 How to Review Requests

**Step-by-Step Review Process:**

**1. Check the Store**
- See which location is requesting
- Consider their sales history
- Know their typical order patterns

**2. Review Current Stock**
- Look at "Current Stock" column
- If they have 50 units and requesting 100 more → verify need
- If they have 5 units and requesting 50 → likely legitimate

**3. Compare to Forecast**
- Look at "Forecasted Demand" column
- Does requested quantity align with forecast?
- Example:
  - Forecast: 80 units
  - Current Stock: 10 units
  - Requested: 70 units
  - **Decision:** ✅ APPROVE (10+70=80, matches forecast)

**4. Consider Lead Times**
- How long until supplier delivers?
- Will store run out before delivery?
- May need to adjust quantity

**5. Check Inventory Availability**
- Do you have it in central warehouse?
- Can supplier provide it?
- Any allocation conflicts?

**6. Make Decision**
- Click "Approve" if all checks pass
- Click "Reject" if concerns exist (with clear reason)

---

#### 📊 Grouping and Organization

**Products Grouped by Store:**
- Easier to review all items from one location together
- See patterns in what each store needs
- Identify stores with higher demand

**Expandable Groups:**
- Click store name to expand/collapse products
- Review one store at a time
- Keep organized with many requests

---

#### 💡 Approval Strategies

**Batch Approval (When Confident):**
- Review all products from a store
- If all look reasonable, approve all at once
- Faster for trusted stores with good track records

**Individual Review (When Cautious):**
- Review each product carefully
- Approve some, reject others
- Use when quantities seem high or unusual

**Partial Approval:**
- You can modify quantities before approving
- Example: Store requests 100, you approve 75
- Use when request is too high but some is justified

---

#### ⚠️ Common Rejection Reasons

**1. "Quantity Exceeds Forecast"**
- Requested amount is more than predictions show
- Example: Forecast shows need for 30, requesting 100

**2. "Insufficient Inventory Available"**
- Central warehouse doesn't have enough
- Supplier can't provide in time

**3. "Budget Constraints"**
- Purchasing budget limits reached
- Need to prioritize other requests

**4. "Recent Replenishment Already Provided"**
- Store received stock recently
- Current stock should be sufficient

**5. "Product Being Discontinued"**
- Item is being phased out
- Don't want to add more inventory

---

#### 📧 Communication with Stores

**After You Approve:**
- Store manager gets notification
- They can see approved quantity
- Purchasing team can proceed with order

**After You Reject:**
- Store manager gets notification with YOUR REASON
- They understand why request was denied
- They can submit new request if needed with adjustments

**Best Practice:**
- Write clear rejection reasons
- Be specific about what needs to change
- Example: ❌ "Too much" → ✅ "Reduce to 50 units to match forecast"

---

#### 📈 Using the Data for Planning

**Identify Trends:**
- Which products are most requested?
- Which stores order most frequently?
- Are forecasts accurate?

**Improve Forecasting:**
- If many requests for a product → forecast may be low
- If lots of rejections → stores may be over-ordering

**Optimize Inventory:**
- High request volume → increase central stock
- Low request volume → reduce safety stock

**Plan Purchases:**
- Aggregate approved requests
- Place bulk supplier orders
- Negotiate better pricing

---

## Tips for Success

### For Store Managers

**✅ Do's:**
- Check forecasts before requesting
- Request only what you need
- Approve your requests promptly
- Monitor current stock regularly

**❌ Don'ts:**
- Don't over-order "just in case"
- Don't wait until completely out of stock
- Don't request without checking forecast
- Don't submit duplicate requests

### For DP Team

**✅ Do's:**
- Review requests daily
- Provide clear rejection reasons
- Consider store's history and needs
- Balance inventory across network

**❌ Don'ts:**
- Don't approve without reviewing
- Don't reject without reason
- Don't ignore urgent requests
- Don't over-allocate inventory

---

## Frequently Asked Questions (FAQ)

### Forecasting Questions

**Q: How often are forecasts updated?**
A: Forecasts are recalculated monthly based on the latest sales data.

**Q: Can I trust the forecast numbers?**
A: Forecasts are based on past sales patterns. They're generally accurate but use your judgment for special circumstances (events, promotions, etc.).

**Q: What if my store is new and has no sales history?**
A: Forecasts for new stores use regional averages or similar store patterns.

### Replenishment Questions

**Q: How long does approval take?**
A: Store approval should be same day. DP approval typically within 1-2 business days.

**Q: What if I made a mistake in my request?**
A: Contact the DP Team immediately. They can reject with a note, and you can submit a corrected request.

**Q: Can I cancel a pending request?**
A: Not directly. Contact your DP Team member to have them reject it.

**Q: Why was my request rejected?**
A: Check the rejection reason in your request details. Common reasons are quantity too high or inventory unavailable.

**Q: How do I know when my order is delivered?**
A: After DP approval, track with your supplier or check with the purchasing team.

**Q: Can I request the same product multiple times?**
A: Not until the first request is processed (approved or rejected).

---

## Getting Help

**Technical Issues:**
- Contact: IT Support
- Email: it@saspulse.com

**Forecasting Questions:**
- Contact: Demand Planning Team
- Email: demand.planning@saspulse.com

**Urgent Stock Needs:**
- Contact: Your DP Team Manager
- Phone: [Insert number]

**Training:**
- Request additional training sessions
- Video tutorials available in Help section

---

## Glossary of Terms

**BTS:** Back-to-School season (main selling period)

**DP Team:** Demand Planning Team (approves replenishment requests)

**Forecast:** Prediction of future sales

**Replenishment:** Process of ordering more stock

**SKU:** Stock Keeping Unit (unique product identifier)

**Style Code:** Internal product code

**Stock Shortage:** Difference between current stock and needed amount (negative = need more)

**Cumulative:** Adding up totals as you go

**Lead Time:** How long it takes for supplier to deliver after ordering

**Safety Stock:** Extra inventory kept "just in case" of unexpected demand

**Stockout:** Running completely out of a product (bad!)

---

## Version History

- **Version 1.0** (March 2024): Initial user guide created
- Guide maintained by: SasPulse Documentation Team
- Last updated: March 10, 2024

---

*This guide is designed for non-technical users. If you need more technical information about system architecture or API details, please refer to the Technical Documentation.*
