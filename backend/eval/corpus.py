"""Synthetic evaluation corpus.

All organisations, products and figures are fictional, so a model cannot answer
from prior knowledge: a correct answer must come from retrieval. Each page is a
list of (kind, text) blocks rendered by build_corpus.py.
"""

NORTHWIND = {
    "filename": "northwind-annual-report-2025.pdf",
    "title": "Northwind Freight Group - Annual Report 2025",
    "scanned": False,
    "pages": [
        [
            ("h1", "Northwind Freight Group"),
            ("sub", "Annual Report 2025 - Fiscal year ended 31 March 2025"),
            ("h2", "Letter from the Chief Executive"),
            ("p", "Fiscal 2025 was the year Northwind stopped being a trucking company with a warehouse "
                  "business attached and became an integrated freight network. Group revenue rose 11.4% to "
                  "$2.83 billion, driven by contract logistics and the full-year contribution of Pellham Cold Chain, "
                  "which we acquired in July 2024 for $412 million."),
            ("p", "Our safety record improved for the third consecutive year. The lost-time injury frequency rate "
                  "fell to 1.9 per million hours worked, down from 2.6 in fiscal 2024. I want to thank every driver, "
                  "picker and planner who made that possible."),
            ("p", "We also made hard choices. We closed the Dunmore cross-dock in Pennsylvania, which had operated "
                  "below 55% utilisation for two years, and consolidated its volume into our Scranton hub. "
                  "Forty-two roles were affected; thirty-one colleagues accepted transfers."),
            ("p", "Looking ahead, our priority is margin, not size. We expect capital expenditure of roughly "
                  "$190 million in fiscal 2026, weighted toward yard automation and battery-electric tractors."),
            ("sig", "Imogen Vasquez-Hart, Chief Executive Officer"),
        ],
        [
            ("h2", "Financial Highlights"),
            ("p", "The table below summarises consolidated results. All figures are in US dollars and are "
                  "audited unless otherwise noted."),
            ("table", [
                ["Metric", "FY2025", "FY2024", "Change"],
                ["Revenue", "$2,830m", "$2,541m", "+11.4%"],
                ["Adjusted EBITDA", "$318m", "$297m", "+7.1%"],
                ["Operating margin", "6.8%", "7.3%", "-0.5 pts"],
                ["Net income", "$121m", "$114m", "+6.1%"],
                ["Free cash flow", "$96m", "$131m", "-26.7%"],
                ["Net debt / EBITDA", "2.4x", "1.9x", "+0.5x"],
            ]),
            ("p", "Operating margin declined by half a point because Pellham Cold Chain operates at lower margins "
                  "than the legacy business during integration, and because of one-off integration costs of "
                  "$23 million. Excluding Pellham, operating margin would have been 7.5%."),
            ("p", "Free cash flow fell mainly because of higher capital expenditure on refrigerated trailers "
                  "and the timing of a large customer payment that slipped into April 2025."),
            ("p", "The Board has recommended a final dividend of 38 cents per share, bringing the full-year "
                  "dividend to 64 cents, an increase of 4 cents on the prior year."),
        ],
        [
            ("h2", "Segment Review"),
            ("h3", "Contract Logistics"),
            ("p", "Contract Logistics generated revenue of $1.21 billion, 43% of the group total. The segment "
                  "operates 61 warehouses totalling 14.2 million square feet. Our largest new contract, "
                  "a seven-year agreement with the home-goods retailer Calloway & Finch, began in October 2024 "
                  "and will be served from a purpose-built facility in Joliet, Illinois."),
            ("h3", "Truckload and Intermodal"),
            ("p", "Truckload and Intermodal revenue was flat at $1.02 billion. Spot rates remained soft through "
                  "most of the year. The fleet ended the year at 3,480 tractors, of which 140 are battery-electric. "
                  "Average tractor age is 3.1 years."),
            ("h3", "Pellham Cold Chain"),
            ("p", "Pellham contributed $600 million of revenue in its first year under Northwind ownership. "
                  "It operates 18 temperature-controlled facilities, principally serving pharmaceutical and "
                  "fresh-food customers. Integration of Pellham's warehouse management system onto the Northwind "
                  "platform is scheduled to complete in the second quarter of fiscal 2026."),
        ],
        [
            ("h2", "Sustainability"),
            ("p", "Scope 1 and 2 greenhouse gas emissions were 612,000 tonnes of CO2-equivalent, a reduction of "
                  "4.8% compared with fiscal 2024 despite higher volumes. Emissions intensity fell to 216 grams "
                  "of CO2e per tonne-kilometre."),
            ("p", "Our target, validated by the Science Based Targets initiative, is a 42% absolute reduction in "
                  "Scope 1 and 2 emissions by fiscal 2032 against a fiscal 2022 baseline. We are currently "
                  "17% below that baseline."),
            ("p", "Rooftop solar now covers 23 of our warehouses with an installed capacity of 31 megawatts. "
                  "The largest single array, at the Joliet facility, is 4.4 megawatts."),
            ("h2", "People"),
            ("p", "Northwind employed 19,750 people at year end, including 6,900 professional drivers. "
                  "Voluntary driver turnover was 38%, compared with an industry average we estimate at 70% to 90%. "
                  "We introduced a guaranteed weekly minimum pay of $1,350 for company drivers in January 2025."),
        ],
        [
            ("h2", "Principal Risks"),
            ("p", "Cybersecurity. A successful attack on our transport management system could halt dispatch. "
                  "In fiscal 2025 we completed migration to a segmented network and achieved ISO 27001 certification "
                  "for our core platforms. We ran two full-scale incident simulations during the year."),
            ("p", "Customer concentration. Our ten largest customers represent 34% of revenue; the largest single "
                  "customer represents 7%. Contracts with eight of the top ten run beyond fiscal 2027."),
            ("p", "Fuel price volatility. Approximately 85% of our truckload revenue includes a fuel surcharge "
                  "mechanism that passes through diesel price changes with a lag of about two weeks."),
            ("p", "Labour availability. Shortages of qualified drivers and warehouse technicians could constrain "
                  "growth. Our Northwind Driver Academy trained 1,140 new drivers in fiscal 2025."),
        ],
        [
            ("h2", "Governance and Outlook"),
            ("p", "The Board comprises nine directors, seven of whom are independent. The Chair is "
                  "Rupert Okonkwo-Lindqvist, who joined the Board in 2019. The Audit Committee met six times "
                  "during the year."),
            ("p", "The external auditor is Hallam Pryce LLP, which has audited the group since fiscal 2021. "
                  "Audit fees for the year were $4.6 million."),
            ("h3", "Fiscal 2026 guidance"),
            ("p", "For fiscal 2026 we expect revenue growth of 4% to 6% and adjusted EBITDA of $335 million to "
                  "$355 million. We expect net debt to EBITDA to return below 2.0x by the end of fiscal 2027. "
                  "Guidance assumes no further acquisitions."),
        ],
    ],
}

HALCYON = {
    "filename": "halcyon-hx200-manual.pdf",
    "title": "Halcyon HX-200 Air-to-Water Heat Pump - Installation and Operation Manual",
    "scanned": False,
    "pages": [
        [
            ("h1", "Halcyon HX-200"),
            ("sub", "Air-to-Water Heat Pump - Installation and Operation Manual - Revision C"),
            ("h2", "1. Safety Information"),
            ("p", "Installation must be carried out by a technician certified to handle refrigerants. The HX-200 "
                  "uses R290 (propane) refrigerant with a charge of 0.95 kg. Keep all sources of ignition at least "
                  "1 metre away from the outdoor unit during servicing."),
            ("p", "Disconnect mains power and wait at least 5 minutes before opening the electrical cover, to allow "
                  "the inverter capacitors to discharge."),
            ("p", "Do not install the outdoor unit in a pit, a basement light well, or any location where escaping "
                  "refrigerant could accumulate below ground level."),
        ],
        [
            ("h2", "2. Technical Specifications"),
            ("table", [
                ["Parameter", "HX-200"],
                ["Heating capacity (A7/W35)", "8.2 kW"],
                ["COP (A7/W35)", "4.85"],
                ["SCOP, average climate, 35 C", "4.62"],
                ["Maximum flow temperature", "70 C"],
                ["Operating range, outdoor air", "-25 C to +43 C"],
                ["Sound power level, outdoor unit", "54 dB(A)"],
                ["Power supply", "230 V, 1 phase, 50 Hz"],
                ["Recommended breaker", "20 A, type C"],
                ["Weight, outdoor unit", "96 kg"],
            ]),
            ("p", "Capacity and efficiency figures are measured according to EN 14511. Actual performance depends "
                  "on installation, emitter design and local climate."),
        ],
        [
            ("h2", "3. Siting the Outdoor Unit"),
            ("p", "Maintain the following minimum clearances: 300 mm behind the unit, 600 mm on the service side, "
                  "and 1,500 mm in front of the fan outlet. Do not obstruct airflow with fences or planting."),
            ("p", "Mount the unit on a level concrete base or the supplied wall brackets, raised at least 150 mm "
                  "above expected snow level. In regions with heavy snowfall, fit the optional snow hood (part "
                  "number HX-SH2)."),
            ("p", "The unit produces condensate during defrost - up to 20 litres per day in cold, humid "
                  "conditions. Route the condensate drain to a soakaway or drain, and fit the drain heater kit "
                  "where temperatures fall below 0 C."),
        ],
        [
            ("h2", "4. Hydraulic Connection"),
            ("p", "Connect flow and return using 28 mm copper or equivalent. The minimum system water volume is "
                  "40 litres; if the heating circuit contains less, install a buffer tank. A strainer of 500 "
                  "microns or finer must be fitted on the return line and is a condition of the warranty."),
            ("p", "Fill the system with clean water to a cold pressure of 1.5 bar. The safety valve opens at 3 bar. "
                  "Use an inhibitor approved for aluminium heat exchangers; glycol concentration, if used, must not "
                  "exceed 30%."),
            ("h2", "5. Commissioning"),
            ("p", "On first power-up the controller runs a 10-minute self-test, during which the compressor will "
                  "not start. Set the heating curve on the controller under Menu > Heating > Curve. For underfloor "
                  "heating, a curve value of 0.4 to 0.6 is typical; for radiators, start at 1.0."),
        ],
        [
            ("h2", "6. Maintenance"),
            ("p", "The homeowner should keep the evaporator fins free of leaves and debris and check the system "
                  "pressure monthly. If pressure falls below 1.0 bar, top up to 1.5 bar."),
            ("p", "A qualified technician must service the unit once every 12 months. The annual service includes "
                  "cleaning the strainer, checking the refrigerant circuit for leaks, inspecting electrical "
                  "terminals, and verifying the defrost cycle."),
            ("h2", "7. Warranty"),
            ("p", "The HX-200 carries a 7-year parts warranty and a 10-year compressor warranty, provided the unit "
                  "is registered within 30 days of installation and serviced annually by an approved installer. "
                  "Labour is covered for the first 2 years only."),
        ],
        [
            ("h2", "8. Troubleshooting"),
            ("table", [
                ["Code", "Meaning", "Action"],
                ["E01", "Low water flow", "Check strainer and circulation pump; bleed air from system"],
                ["E04", "High pressure trip", "Check flow temperature setpoint and that valves are open"],
                ["E07", "Outdoor sensor fault", "Check sensor wiring at terminal X4"],
                ["E12", "Communication lost", "Check bus cable between indoor and outdoor units"],
                ["E19", "Defrost failure", "Clear ice manually; contact installer if repeated"],
            ]),
            ("p", "If error E04 occurs more than three times in 24 hours, the unit locks out and must be reset "
                  "by holding the OK and Back buttons together for 10 seconds."),
        ],
    ],
}

MERIDIAN = {
    "filename": "meridian-hybrid-work-policy-scanned.pdf",
    "title": "Meridian County Council - Hybrid Working Policy",
    "scanned": True,
    "pages": [
        [
            ("h1", "Meridian County Council"),
            ("sub", "Hybrid Working Policy - HR-POL-114 - Effective 1 February 2025"),
            ("h2", "1. Purpose and Scope"),
            ("p", "This policy sets out how employees of Meridian County Council may divide their working time "
                  "between council premises and an approved home location. It applies to all permanent and "
                  "fixed-term employees who have completed their probationary period of six months."),
            ("p", "Roles that require a physical presence, including depot staff, care workers and front-desk "
                  "customer service, are not eligible for hybrid working under this policy."),
        ],
        [
            ("h2", "2. Attendance Requirements"),
            ("p", "Eligible employees must work from a council building for a minimum of two days per week, "
                  "averaged over a four-week period. Each team must designate one anchor day per week on which "
                  "all team members attend in person."),
            ("p", "Hybrid arrangements must be agreed in writing with the line manager using form HR-114A and "
                  "reviewed at least every twelve months."),
            ("h2", "3. Equipment and Expenses"),
            ("p", "The Council will provide a laptop, headset and one external monitor. Employees may claim a "
                  "one-off home-office allowance of 250 pounds toward a desk or chair, supported by receipts, "
                  "within the first three months of an approved arrangement."),
            ("p", "The Council does not reimburse home energy or broadband costs."),
        ],
        [
            ("h2", "4. Working Abroad"),
            ("p", "Employees may work from outside the United Kingdom for no more than 10 working days in any "
                  "calendar year, subject to prior approval from their Head of Service and a tax and data "
                  "protection check by HR. Working from countries without a UK data adequacy decision is not "
                  "permitted."),
            ("h2", "5. Health and Safety"),
            ("p", "Employees must complete the display screen equipment self-assessment within two weeks of "
                  "starting hybrid working and annually thereafter. Accidents at home while working must be "
                  "reported through the normal incident system within 24 hours."),
        ],
        [
            ("h2", "6. Review and Appeals"),
            ("p", "A manager may end a hybrid arrangement with four weeks' written notice where business needs "
                  "change or performance concerns arise. An employee may appeal a refusal or termination to the "
                  "Head of Service within 14 calendar days."),
            ("p", "This policy will be reviewed by the Director of People Services in January 2027."),
            ("sig", "Approved by the Employment Committee, 9 December 2024"),
        ],
    ],
}

DOCUMENTS = [NORTHWIND, HALCYON, MERIDIAN]
