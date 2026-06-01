# Austin Luu
Toronto, Canada · austinowenluu@gmail.com · +1-416-451-3338 · https://www.linkedin.com/in/austin-luu · https://github.com/austinluu · https://austinluu.me

## Summary
Software Development Engineer II at ViTAA Medical Solutions, with scope spanning ML platform and cloud infrastructure, IT administration and security, forward-deployment engineering at clinical sites, and regulatory/quality work (FDA 510(k), ISO 13485, SaMD) for a medical-imaging product. Builds agentic AI and automation tooling — including multi-agent development pipelines, AI governance/SBOM systems, and standalone Claude skills — on a foundation in computer vision, data analytics, predictive modeling, and AWS cloud infrastructure. Also Founder & CEO of two businesses (web development and AI process automation; a cafe pop-up), with a background in mechatronics/robotics engineering and a long-running competitive robotics leadership record. Mechatronics Engineering graduate of Toronto Metropolitan University (formerly Ryerson University).

## Skills
- **Languages:** Python, Java, JavaScript, TypeScript, C, C++, SQL, NoSQL, MATLAB, Octave, VBA, VHDL, Ladder Logic, LaTeX
- **Web / Frontend:** HTML, CSS/SCSS, React.js, Next.js, jQuery, Node.js, Bootstrap, npm, Django
- **Data / ML libraries:** PyTorch, TensorFlow, Scikit-Learn, Pandas, NumPy, SciPy, Matplotlib, Seaborn, Jupyter Notebook
- **ML / Deep Learning:** Convolutional Neural Networks (CNNs), Recurrent Neural Networks (RNNs), Transformers, Statistical Analysis, Linear/Logistic Regression, SVM, K-Means Clustering, Regularization, Hyperparameter Tuning, Adam
- **NLP:** NLTK, BERT, GPT-3, NLP, NLU
- **Computer Vision:** OpenCV, SimpleCV, YOLO, ResNet-50, U-Net, Image Recognition
- **Cloud / Infra:** AWS (S3, EC2, Lambda, CodeDeploy, CloudWatch, IAM), GCP, Docker, Slurm, Unix/Linux, Bash, Git
- **Databases:** SQL, NoSQL, SQLite
- **Design / CAE / CAD:** SolidWorks (CSWA Certified), AutoCAD, Autodesk Inventor, GrabCAD, ANSYS, GMSH, SOFA, FMEA
- **Manufacturing / Hardware:** FDM 3D Printing, Laser Cutting, Turning, Milling, Drilling, Arc & MIG Welding, Soldering, Arduino (Mega / 101), MQTT Protocol, OMRON PLC
- **BI / PLM / Tools:** Microsoft Office (Excel), Power BI, Tableau, CRM, Navision, Salesforce, ENOVIA, Teamcenter PLM, Jira, Confluence, Notion, Figma, Adobe Photoshop, WordPress CMS, Bluehost, Google Maps API, web scraping
- **AI / Agentic:** Claude Code / Claude Skills, MCP (Model Context Protocol), AI agent orchestration & subagent-driven SDLC, dynamic context engineering, AI process/workflow automation, evaluation harnesses & rubrics, progressive-disclosure architecture, AI governance
- **Security / IT:** CrowdStrike Falcon (Falcon Insight / EDR), Syxsense, endpoint management & protection, USB device control, firewall management, static code analysis
- **Healthcare / Imaging:** DICOM, PACS, PHI de-identification
- **Regulatory / Quality:** HIPAA, PHIPA, FDA 510(k), ISO 13485, SaMD, QMS, design controls, V&V, SBOM, SOC 2, PCI-DSS

---

## Experience

### Software Development Engineer II — ViTAA Medical Solutions
*Montreal, Canada · June 2024 – Present*

**Context:** Builds and operates the machine learning platform and cloud infrastructure for a regulated medical-imaging product (Software as a Medical Device), with expanded scope spanning IT administration and security, Forward Deployment Engineer Lead duties at clinical sites, regulatory/quality work (FDA 510(k), ISO 13485), and org-wide AI governance and development automation.

**Accomplishments:**

- **X:** Led project planning and execution to design and build a scalable machine learning platform enabling rapid, concurrent development and deployment of diverse models, with datasets in AWS S3 and distributed training and inference on EC2 high-performance compute nodes.
  **Y:** Reduced new-model deployment time by 80% (5 days → 1 day).
  **Z:** AWS S3 for datasets; distributed, concurrent training/inference on EC2 HPC nodes, replacing the previous sequential deployment process.

- **X:** Owned an architectural redesign that rebuilt the data pipelines and added parallel execution, reducing runtime.
  **Y:** Runtime reduced by 39%.
  **Z:** Slurm-managed data pipelines on AWS EC2 HPC nodes; parallel execution via Python multiprocessing and multithreading.

- **X:** Implemented an automated event-driven workflow with access controls, monitoring/alerting, and failure handling, reducing operational downtime.
  **Y:** Operational downtime reduced by a projected 67%.
  **Z:** AWS Lambda integrated with EC2 and S3; IAM-based access controls; CloudWatch monitoring and alerting; failure handling.

- **X:** Built reusable internal tooling and libraries that standardize data ingestion, model training, and deployment workflows, accelerating experimentation and reducing engineering overhead.
  **Y:** Cut experiment setup time by 85%, enabling up to 5× higher experiment throughput; adopted by 10 engineers across 2 teams and 4 projects.
  **Z:** Reusable internal tooling/libraries standardizing ingestion, training, and deployment workflows.

- **X:** Established production monitoring, alerting, and automated recovery across data processing and backend services, improving system reliability and reducing incident response time.
  **Y:** Increased monitoring and automated-recovery coverage from 0 to 100% of services; reduced incident count by 80%, mean time to detect by over 90%, and recovery time by over 80%.
  **Z:** Production monitoring, alerting, and automated recovery across data-processing and backend services.

- **X:** Took on IT administration, deploying and managing endpoint management and protection across all company devices.
  **Y:** 100% of devices managed across 30+ endpoints at 99.8% compliance; patch-driven device downtime reduced by over 90% with zero business downtime.
  **Z:** Syxsense for endpoint management; CrowdStrike Falcon lightweight agent for endpoint protection.

- **X:** Detected, investigated, and remediated high-priority security alerts.
  **Y:** Mean time to resolution (MTTR) reduced by 35%.
  **Z:** CrowdStrike Falcon Insight (EDR).

- **X:** Built and tuned custom prevention policies, USB device control, and firewall rules to eliminate false positives and harden network defenses.
  **Y:** Contributed to achieving SOC 2 compliance.
  **Z:** CrowdStrike Falcon console.

- **X:** As Forward Deployment Engineer Lead, built and maintained DICOM ingestion pipelines that pulled dynamic CT studies from hospital imaging systems into a cloud analysis platform, handling de-identification and PHI-safe transfer in compliance with HIPAA/PHIPA.
  **Y:** Ingested 200+ CT studies (over 1 TB of scan data) from 5 hospital sites.
  **Z:** DICOM ingestion pipelines; de-identification and PHI-safe transfer; HIPAA/PHIPA compliance.

- **X:** Built tooling and custom connectors to bridge ViTAA's cloud platform with heterogeneous hospital IT systems spanning varying PACS vendors and network/security configurations, reducing per-site integration effort.
  **Y:** Cut per-site integration time by 83% across 4 integrated sites.
  **Z:** Custom connectors and tooling for heterogeneous PACS vendors and network/security configurations.

- **X:** Documented deployments and integrations within an FDA 510(k) / ISO 13485 quality framework to meet regulatory and design-control requirements.
  **Y:** Produced 20+ design-control documents.
  **Z:** FDA 510(k) / ISO 13485 design-control documentation.

- **X:** Triaged and resolved field issues for clinical software under Software-as-a-Medical-Device (SaMD) constraints, maintaining audit-ready records of every change.
  **Y:** Triaged and resolved 30+ field issues during a pilot, averaging 1-hour resolution at a 97% resolution rate.
  **Z:** SaMD field-issue triage; audit-ready change records.

- **X:** Prototyped workflow automations that eliminated manual steps in pre-operative aortic planning, reinforcing the platform's core value of planning consistency and time savings for physicians.
  **Y:** Removed 3 manual steps, reducing planning turnaround time by 38%.
  **Z:** Workflow-automation prototyping for pre-operative aortic planning.

- **X:** Designed and built a model- and provider-agnostic dynamic context system that assembles, scopes, and prunes context at runtime, deployed across 4+ projects, measurably improving output quality and consistency.
  **Y:** Token consumption cut by 82–87%; deployed across 4+ projects.
  **Z:** Model- and provider-agnostic runtime context assembly, scoping, and pruning.

- **X:** Led org-wide AI governance and policy development, and built an automated verification & validation (V&V) tool that inventories, vets, and tracks AI tools, plugins, and extensions, auto-generating a software/AI bill of materials (SBOM) for supply-chain traceability and audit readiness, aligned with emerging FDA medical-device cybersecurity/SBOM requirements.
  **Y:** Inventoried and tracked 15 AI tools at 100% coverage; established 2 AI governance policies.
  **Z:** Automated V&V tooling; AI/SBOM generation; AI governance and policy development.

- **X:** Automated Quality Management System (QMS) document generation, improving consistency and audit-readiness in a regulated ISO 13485 / FDA context.
  **Y:** QA and engineering documentation effort reduced by 91%.
  **Z:** QMS document-generation automation.

- **X:** Built an automated, subagent-driven AI development pipeline that feeds requirements and tickets into a coordinated team of specialized AI agents running the SDLC, shifting engineers and PMs toward reviewing PRs and curating workflow inputs rather than writing code line-by-line.
  **Y:** Development time reduced by 88%.
  **Z:** MCP servers integrated with Confluence/Jira connectors; subagent-driven SDLC with an orchestrator/engineering-manager agent plus senior-staff-engineer, developer, code-reviewer, test-writer, QA/V&V, documentation, and security/SBOM agents.

- **X:** Mentored and onboarded 2 junior engineers, pairing on code reviews and providing structured technical guidance across architecture and debugging, bringing both to independent feature ownership.
  **Y:** 2 junior engineers brought to independent feature ownership within 3 months.
  **Z:** Pair programming, structured code review, and architecture/debugging guidance.

---

### Software Development Engineer I — ViTAA Medical Solutions
*Montreal, Canada · June 2022 – June 2024*

**Context:** Software engineering on a medical-imaging codebase, including 3D cardiovascular auto-segmentation models and foundational engineering standards.

**Accomplishments:**

- **X:** Defined and implemented core data structures and coding standards across the codebase, improving correctness, maintainability, onboarding velocity, code quality, and review efficiency. (Earlier resumes phrase this as "spearheaded establishment of code standards, improving code velocity, maintainability, and testability.")
  **Y:** Reduced new-engineer ramp-up time from 3 weeks to 1 week; cut PR review time and review cycles per PR by over 50% each; brought 10+ modules to the new standard.
  **Z:** Core data structures and coding standards established across the codebase.

- **X:** Designed custom PyTorch UNets for 3D cardiovascular auto-segmentations across four domains, reducing QA personnel manual adjustments.
  **Y:** 92.84% Dice score; QA adjustments reduced by over 27%.
  **Z:** Custom UNet architectures in PyTorch, applied across four segmentation domains.

- **X:** Developed an automated CI/CD integration pipeline, reducing test execution times.
  **Y:** Test execution times reduced by 43%.
  **Z:** AWS CodeDeploy, EC2, and S3.

- **X:** Implemented a parallel-computing, infrastructure, and software-architecture overhaul, reducing product execution time.
  **Y:** Product execution time reduced by 30%.
  **Z:** Parallel computing with Python multiprocessing and multithreading; infrastructure and software-architecture overhaul.

- **X:** Established and provided training for an automated unit-testing framework for a team of engineers.
  **Y:** 300+ tests across 10+ components; team of 10+ engineers.
  **Z:** Automated unit-testing framework.

---

### Founder & CEO — Cafe Toast
*Toronto, Canada · June 2025 – Present*

**Context:** Cafe pop-up business operating across the Greater Toronto Area.

**Accomplishments:**

- **X:** Ran a cafe pop-up business at markets, conventions, and wedding events across the GTA.
  **Y:** Served over 1,000 customers and sold over 2,000 items across 6+ events, generating over $10,000 in revenue.
  **Z:** Market and convention pop-ups; wedding-event service.

- **X:** Launched a clothing line for the business.
  **Y:** Over $1,000 in merch sales.
  **Z:** _(no method detail in source.)_

---

### Founder & CEO — August Technologies
*Toronto, Canada · Sept. 2021 – Present*

**Context:** Web development services and AI process automation for small businesses.

**Accomplishments:**

- **X:** Developed and managed websites for 4 small-business clients and automated their CRM and payroll workflows.
  **Y:** Over 90% reduction in logistics/operational time; 100% recurring clients.
  **Z:** Web development; CRM and payroll automation.

- **X:** Built AI process-automation tooling for clients.
  **Y:** 4+ automations delivered.
  **Z:** AI process automation.

---

### Senior Analyst — CIBC
*Toronto, Canada · Mar. 2022 – June 2022*

**Context:** Project consulting on a business banking transformation initiative.

**Accomplishments:**

- **X:** Served as a key project consultant for a business banking transformation initiative, advising project teams and stakeholders on best practices and strategies to achieve project objectives.
  **Y:** Advised on a $50M transformation initiative, supporting 100+ stakeholders across 6+ teams.
  **Z:** Project consulting; stakeholder and project-team advisory.

- **X:** Developed comprehensive project assessment reports and process charts outlining insights and recommendations for project enhancements, resource allocation, and timeline adjustments, streamlining the project timeline and unblocking development.
  **Y:** Produced 4 assessment reports and process charts.
  **Z:** Project assessment reports; process charts.

- **X:** Facilitated knowledge-sharing sessions and provided training to equip team members and stakeholders with the skills and knowledge to support project success.
  **Y:** Trained 10 senior bank tellers across 3 sessions each.
  **Z:** Knowledge-sharing sessions; training.

---

### Data Analyst — TOHacks
*Toronto, Canada · Jan. 2022 – June 2023*

**Context:** Hackathon organization; analytics to improve participant submissions and engagement.

**Accomplishments:**

- **X:** Analyzed prior years' user submission data to guide data-driven business decisions and increase participant submissions through a data-supported admission process. (Earliest resume phrases this as "working on increasing future participant submission rate through a data supported admission process," with no metric.)
  **Y:** Registrations increased by 84%; user engagement increased by 23%.
  **Z:** Python, Seaborn, and Pandas.

- **X:** Conducted A/B testing to assess the impact of various design decisions, increasing user conversion.
  **Y:** 20% increase in user conversion.
  **Z:** A/B testing of design decisions.

---

### Process Engineer — AlphaPoly Packaging
*Brampton, Canada · June 2021 – Oct. 2021*

**Context:** Manufacturing operations and quality at a packaging company.

**Accomplishments:**

- **X:** Analyzed manufacturing operation data and redeveloped standard operating procedures for operational machines, forecasting a reduction in operation downtime.
  **Y:** Forecasted 65% reduction in operation downtime.
  **Z:** Power BI and Excel.

- **X:** Developed end-to-end quality testing across all manufacturing departments, reducing quality cases. (Also phrased as designing end-to-end quality testing protocols for all manufacturing processes.)
  **Y:** June-to-September quality cases reduced by 31%.
  **Z:** End-to-end quality testing across all manufacturing departments.

- **X:** Led product development to acquire new machine tooling, expanding product variability and enabling sustainable materials development, including compostable, renewable, and post-consumer recycled materials.
  **Y:** Managed a $1M capital budget and acquired 4 unique new tools, increasing product variability by over 20%.
  **Z:** New machine tooling acquisition; sustainable materials development.

---

### Product Data Analyst — Celestica
*Toronto, Canada · May 2019 – June 2021*

**Context:** Aerospace & Defense product data management and value engineering; global cross-functional sourcing.

**Accomplishments:**

- **X:** Initiated and led Aerospace & Defense value-engineering cost-saving initiatives, reducing excess inventory and expanding the customer AVL (Approved Vendor List) portfolio.
  **Y:** Excess inventory reduced by over 20%; AVL portfolio expanded by over 15%; ~$1.5M annual savings.
  **Z:** Analysis with Tableau, Power BI, and Excel; end-of-life and alternate-component analysis (per the manufacturing/aerospace resume).

- **X:** Analyzed customer portfolio data to identify demonetized product developments and assess the impact of commodity price changes.
  **Y:** Over $5 million in customer portfolio data analyzed.
  **Z:** SQL, Tableau, Power BI, and Excel.

- **X:** Coordinated and managed global Aerospace & Defense cross-functional sourcing projects across buying, sourcing, design, manufacturing, quality engineering, commodity management, and planning departments to enable material procurement and manufacturing (manufacturing/aerospace resume adds alignment with CGP and ITAR regulations).
  **Y:** $5 million in global sourcing projects.
  **Z:** Cross-functional coordination across procurement, engineering, and planning functions.

- **X:** Developed VBA macros for consolidating and analyzing performance-metric reports, scrubbing customer BOMs for product data management, and neural-network predictive analysis of component cost based on description.
  **Y:** Saved team members over 20 hours per week and increased customer component-processing throughput by over 30%; cost-prediction model achieved 92% accuracy within a 5% cost tolerance.
  **Z:** VBA macros; CRM and Power BI for performance-metric reporting; neural-network model for component-cost prediction.

---

### Robotics Engineer Lead — Ryerson Rams Robotics
*Toronto, Canada · Sept. 2016 – June 2021*

**Context:** Competitive university robotics team; led design, simulation, and software for autonomous competition robots.

**Accomplishments:**

- **X:** Led an agile team in the design and development of an autonomous robot with PID control, placing first nationally at the 2018 & 2019 VEXU competitions. (Manufacturing/aerospace resume adds the robot was capable of expanding 150 cm in height, repetitive lifting of 10 lb, and omni-directional drive; 2025 resume phrases this as owning software architecture and delivery for the autonomous C++ control system.)
  **Y:** Team of 15; 1st nationally (2018 & 2019 VEXU); 150 cm expansion; 10 lb repetitive lift.
  **Z:** Agile team leadership; PID control developed in C++.

- **X:** Piloted development of dynamic (and static) force-model simulations to improve structural integrity, placing second internationally at URC2019.
  **Y:** Structural integrity increased by over 35%; 2nd internationally (URC2019).
  **Z:** MATLAB and ANSYS FEA simulations.

- **X:** Redeveloped the system architecture of rocker-bogie differential mechanisms, decreasing weight and moment forces for the URC2019 competition.
  **Y:** 2nd internationally (URC2019).
  **Z:** SolidWorks and ANSYS FEA.

- **X:** Designed and manufactured an autonomous science console for life detection on Mars, comprised of an auger intake and centrifuge carousel storage.
  **Y:** Stored 6 soil samples on the centrifuge carousel and ran 6 detection protocols.
  **Z:** Detection protocols including ATP Bioluminescence and Ninhydrin tests.

---

### Research Assistant — Ryerson University
*Toronto, Canada · Sept. 2020 – Jan. 2021 (title conflict — see Conflicts)*

**Context:** Soft-robotics research; soft continuum arm for UAV application.

**Accomplishments:**

- **X:** Re-evaluated project requirements and led mechanical design ideation for a soft robotic continuum arm application on UAVs, drawing inspiration from hydrostatic skeletons and muscular hydrostat structures found in nature.
  **Y:** Evaluated 5 design concepts and contributed to a literature review toward publication.
  **Z:** Mechanical design ideation; biomimetic design approach; literature review toward publication in aerial manipulation systems.

- **X:** Designed, modeled, and simulated a 20-degrees-of-freedom soft robotic continuum arm — giving a near-fluid range of motion — to analyze its mechanical behaviour.
  **Y:** Modeled 20 degrees of freedom and ran over 50 simulations.
  **Z:** SolidWorks for modeling; FEA in GMSH, SOFA, and ANSYS.

---

### Lead Web Developer — Home Staging by K
*Brampton, Canada · Sept. 2016 – Dec. 2018*

**Context:** Web services and applications for a home-staging business.

**Accomplishments:**

- **X:** Led planning, design, and implementation of new and existing web services and applications, including an online report pipeline and a user-friendly front end.
  **Y:** Delivered 5 web services and improved page load times by 56%.
  **Z:** JavaScript, CSS, HTML; WordPress CMS.

- **X:** Applied evaluation and development of technical enhancements and modifications, increasing the user pool.
  **Y:** 20% increased user pool.
  **Z:** _(no method detail in source.)_

---

## Projects

### Coda
*Personal · 2026*

- **X:** Designed and built a suite of Claude Code skills that statically inspect a repository and auto-generate auditor-ready draft documentation for SOC 2, HIPAA, and PCI-DSS, automating the evidence-collection and narrative-writing of audit prep normally done by hand over weeks.
  **Y:** Built 4 distinct skills across 3 compliance frameworks (SOC 2, HIPAA, PCI-DSS), with additional frameworks and skills in development.
  **Z:** Claude Code skills; static code inspection; SOC 2 / HIPAA / PCI-DSS frameworks.

- **X:** Went beyond configuration-state tools (Vanta, Drata, Secureframe) by reading application code to verify how controls are actually implemented — locating auth enforcement, data flows, and cryptography in use — and mapped specific lines of code to control criteria to produce traceable, evidence-backed control narratives, turning the codebase into a primary audit-evidence source.
  **Y:** Works at any repo scale; supports 5 language/framework stacks (Express, Django, Go, Java/Spring, Rails), with more in development.
  **Z:** Static application-code analysis; code-to-control-criteria mapping; control-narrative generation.

---

### Satellite
*Personal · 2026*

- **X:** Designed and built a self-contained Claude Skill orchestrating a multi-agent investment-analysis workflow that screens 20–30 candidates down to 8–12 finalists per run, packaging two opposing strategy engines (V4.1 asymmetric-swing and V4.1-Q quality-compounder) with matched evaluation rubrics into a single distributable artifact with progressive-disclosure architecture.
  **Y:** 2 strategy engines orchestrating 11 specialized subagents (5–6 per engine).
  **Z:** Self-contained Claude Skill; multi-agent orchestration; progressive-disclosure architecture.

- **X:** Engineered a degradation-tolerant data layer that falls back from a primary financial-data API to a secondary source and web/filings scraping when tier limits are hit, with mandatory per-field source tagging and explicit "unavailable" flagging to prevent silent data fabrication.
  **Y:** 3-tier data fallback (primary API → secondary source → web/filings scraping) with per-field source tagging.
  **Z:** Multi-tier data fallback; per-field source tagging.

- **X:** Diagnosed and fixed two systematic logic defects in the screening criteria through iterative pilot testing — a bright-line rule that excluded valid candidates and a single-path qualifier that mis-rejected an entire class of inputs — refactoring them into multi-pathway conditional logic with documented exceptions.
  **Y:** 2 systematic logic defects fixed.
  **Z:** Iterative pilot testing; multi-pathway conditional refactor.

- **X:** Built a strict pass/fail validation harness (hard gates, weighted scoring, automatic deductions) that rejected the system's own output until quality thresholds were met, driving measurable quality improvement across iterations.
  **Y:** Rubric scores rose from 69→86 and 74→81 after calibration changes.
  **Z:** 2 per-engine evaluation rubrics, each with 10 hard pass/fail gates, 9 weighted scored categories (100 points), and a red-flag deduction list.

- **X:** Authored comprehensive specification and handoff documentation enabling stateless resumption across sessions, and validated trigger reliability through positive and negative test cases before packaging.
  **Y:** Validated trigger reliability across 4 positive/negative test cases (4/4 pass).
  **Z:** Spec + handoff docs; positive/negative trigger test cases.

---

### RoadCV
*DeepLearning.AI · 2022*

- **X:** Developed a car detection system to detect and draw bounding boxes around potential classes for a self-driving car.
  **Y:** 80 potential classes.
  **Z:** YOLO in TensorFlow.

---

### Kabo
*Hack The North 2020++ · 2021 · https://devpost.com/software/karaokebot*

- **X:** Designed and implemented an AI-driven Discord bot that simulates karaoke with real-time speech recognition and pitch & lyrical accuracy scoring.
  **Y:** Achieved 5 ms processing latency and supported over 50,000 songs.
  **Z:** Python (back end) and JavaScript (front end); Aubio, NumPy, SpeechRecognition, Pydub, LyricsGenius, and Wave for audio analysis; Node.js, Discord.js, and PythonShell for interfacing.

---

### Bionic Arm
*Team project @ Ryerson Rams Robotics · 2019*

- **X:** Designed and fabricated a servo-driven, 15-degrees-of-freedom bionic/prosthetic arm assembly capable of lifting a load.
  **Y:** $150 build cost; 15 degrees of freedom; 5 lb lifting capacity.
  **Z:** PID control on an Arduino Mega; C++; SolidWorks and ANSYS; 3D printing.

---

### Parallel Computing Drone Swarm
*PennApps Hackathon (PennApps XVIII) · 2018 · https://devpost.com/software/drone-swarm*

- **X:** Designed and built a hazard-detection 2D mapping robot / IoT drone network that collects thermal, moisture, and relative-location data from two autonomous IoT ground drones, producing 2D maps for search-and-rescue planning.
  **Y:** Top 20th percentile of participants.
  **Z:** Python, C++, MQTT Protocol, Arduino 101s, laser cutting, and 3D printing.

---

### Portable Machine Shop
*Capstone project @ Ryerson University · 2021*

- **X:** Designed a portable machine shop for contract manufacturing, maintenance, and competitive engineering design teams, for machining small metal and plastic parts via milling, turning, and drilling.
  **Y:** $4,400 design cost.
  **Z:** Custom extruded sheet-metal cabinet with a COTS mill and lathe, stowable add-on tool shelves, and a built-in winch and ramp; top-down FMEA, human-factor considerations, and static-loading FEA for component validation.

---

### Helmet Impact Tester
*Term project @ Ryerson University · 2020*

- **X:** Designed a machine for testing safety helmets' factor-of-safety, impacting helmets across multiple locations.
  **Y:** Impacts at 28 m/s with a force of 60 N across six impact locations.
  **Z:** Three pneumatic-piston end-effector mechanisms; simulated on an OMRON PLC using PLC Fiddle ladder-logic software.

---

### RUKPOP
*Web application · 2019 · http://rukpop.com/ (also ruk-pop.weebly.com)*

- **X:** Piloted design and development of end-to-end web applications for Ryerson University's "Korean Pop Culture" student organization, covering sponsorship, navigation, event updates, and communication; maintained, optimized, troubleshot, and improved the applications.
  **Y:** Managed 8–12 events annually, reaching over 5,000 students with 1,000+ monthly site visits.
  **Z:** Mobile-first web application in JavaScript, CSS, and HTML; managed on Bluehost.

---

### Greeco
*RU Hacks · 2018 · https://greeco.tech/*

- **X:** Designed and developed a crowd-sourced web application that lets users rate locations and create a visual "cleanliness" overlay of their surroundings, to raise awareness and identify problematic areas for community cleanup events.
  **Y:** Covered the entire Greater Toronto Area, collecting data points for over 30 sites.
  **Z:** HTML, CSS, JavaScript, Python, Django, SQLite, and Google Maps API.

---

### Vision Motion
*THacks2 · 2017 · https://visionmotion.williamqin.com/*

- **X:** Built a real-time mobile computer-vision tool that tracks and graphs the projectile motion of an object.
  **Y:** Ran at 60 fps with 98.4% tracking accuracy and ~1 s latency.
  **Z:** OpenCV on mobile devices.

---

## Education

### B.Eng Mechatronics Engineering, Toronto Metropolitan University (formerly Ryerson University)
*Toronto, Canada · Sept. 2016 – Apr. 2021*

- GPA: 3.70; Dean's Honour List.
- Awards: Robotics International Society of Manufacturing Engineers Award; Mechanical Eng. (First Year) Alumni Award.
- Relevant coursework (varies by resume): Data Structures & Algorithms, Digital Systems, Control Systems / Real-Time Computer Control Systems, Intelligent Systems, Linear Algebra, Statistics.


### Deep Learning Specialization, DeepLearning.AI
*Remote · Dec. 2021 – Jan. 2022*

- Coursework: Neural Networks, Hyperparameter Tuning, Regularization and Optimization, Machine Learning Project Structure, Convolutional Neural Networks, and Sequence Models.

---

## Certifications / Additional

- **Project Management Professional (PMP), PMI — 2026** (as listed on the 2025 SWE resume / LaTeX source).
- **Google Project Management Specialization — 2024** (listed on the 2024 resumes; commented out in the latest LaTeX source — see Notes).
- **DeepLearning.AI Deep Learning Specialization — 2021–2022** (also detailed under Education).
- **SolidWorks CSWA Certified** (from the manufacturing/aerospace resume).
- **Engineering Judge, Brampton Robotics — 2022 – Present:** Evaluated regional and provincial robotics teams on engineering design and system performance.

---

## Conflicts to resolve

None — all conflicts resolved by the candidate.

## Items missing a metric (Y)

None — every accomplishment now has a confirmed Y supplied by the candidate.

## Notes

- **Sources used:** EMERALD resume (image, file `1643124941564.jpg` / `Austin_Luu_Resume_2019_CS_EMERALD.pdf`), `Austin_Luu_Resume_2022_R.pdf`, `Austin_Luu_Resume_2022_R__1_.pdf`, `Austin_Luu_Resume_2022_P.pdf`, `Austin_Luu_Resume_2022_ManufacturingAerospace.pdf`, `Austin_Luu_Resume_2024_SWE.pdf`, `Austin_Luu_Resume_2024_ML.pdf`, `Austin_Luu_Resume_2025_SWE.pdf`, and the LaTeX sources `education.tex`, `experience.tex`, `skills.tex`, `projects.tex` (the source behind the 2025 SWE resume).
- **The `.tex` files** match the 2025 SWE resume. Their commented-out (inactive) sections contain alternate phrasings and a few items not in any rendered resume — I did **not** treat commented-out LaTeX as kept accomplishments. Items found only in commented LaTeX that you may want to use: a Research Assistant bullet — "Led literature review and application towards research publication of potential technologies in Aerial Manipulation Systems"; and the project links I did surface above (RUKPOP/Greeco/Vision Motion/Kabo/Drone Swarm).