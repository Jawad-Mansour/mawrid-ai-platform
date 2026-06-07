Here is the **complete, detailed master topic list** formatted specifically for Claude. This document gives Claude full context on everything you've covered in the bootcamp so he can intelligently discuss project ideas with you.

---

# AI ENGINEERING BOOTCAMP – COMPLETE TOPIC REFERENCE FOR CLAUDE

*Use this document to understand everything the user has learned. Every topic from all 62 files across Weeks 1-8 is captured below with technical details.*

---

## HOW TO USE THIS DOCUMENT

I have completed an 8-week AI Engineering Bootcamp covering:
- Classical ML (regression, classification, feature engineering)
- Deep Learning (neural networks, CNNs, transfer learning)
- NLP (text representations, transformers, fine-tuning)
- Computer Vision (image classification, detection, segmentation)
- RAG (naive to advanced: parent-doc, multi-vector, HyDE, graph, re-ranking)
- Agentic AI (tool calling, ReAct, LangGraph, multi-agent)
- MLOps (model registry, validation, observability, drift detection)
- Production patterns (queues, idempotency, outbox, guardrails)
- Eval-driven development (tests vs evals, RAGAS, LLM-as-judge)
- Infrastructure (Docker, AWS, FastAPI, Ollama, GGUF)
- Prompt Engineering (all techniques from zero-shot to ReAct)
- Software engineering (spec-driven dev, clean architecture, transactions)

When I suggest project ideas, draw on any of these topics. I understand the trade-offs between approaches and can implement production-grade systems.

---

## WEEK 1: MACHINE LEARNING FOUNDATIONS & EDA

### 1.1 Artificial Intelligence Fundamentals
- **Definition**: AI creates systems that perform tasks requiring human intelligence (learning, reasoning, problem-solving)
- **Key branches**: Machine Learning (learns from data), NLP (human language), Computer Vision (visual information), Generative AI (creates new content)
- **ML limitations**: cannot predict with certainty (only probabilities), cannot work without data, correlation ≠ causation, cannot replace domain expertise, cannot make ethical decisions independently

### 1.2 Supervised Learning
- **Definition**: Predict a specific value from labeled training data
- **Classification**: Predict categories (weather type, will customer buy, will patient be readmitted)
- **Regression**: Predict exact values (temperature, customer spend, patient stay length)
- **Labels**: Every training example needs correct answer; labeling is expensive, slow, and sometimes inconsistent
- **Good dataset criteria**: Size (more examples), Quality (garbage in, garbage out), Representativeness (reflects real world), Balance (all categories represented)

### 1.3 Traditional Programming vs Machine Learning
- **Traditional**: Human writes explicit rules (IF humidity > 80% AND wind > 20 km/h THEN Rainy) – breaks when rules don't match reality
- **ML**: Data reveals rules; model discovers patterns from thousands of examples; generalizes to new, unseen situations

### 1.4 How a Model Learns (The Learning Loop)
1. Make prediction using current internal parameters
2. Compare prediction to true answer
3. Measure the error (how wrong was it?)
4. Adjust internal parameters to reduce error
5. Repeat thousands of times until error is minimized
- **The model asks**: "How wrong am I, and in which direction?"

### 1.5 Underfitting vs Overfitting
- **Underfitting**: Model too simple, high bias, fails to capture patterns
- **Overfitting**: Model too complex, high variance, memorized training data
- **Goal**: Both scores close and both acceptable

### 1.6 The ML Lifecycle
Complete pipeline from problem framing → data collection → EDA → preprocessing → model training → evaluation → deployment → monitoring

### 1.7 Data Foundations
- **Data sources**: Questionnaires, surveys, interviews, social media activity, transactions, sensors/IoT, web scraping, government records
- **Storage**: Local files, cloud storage, public URLs, built-in datasets
- **Formats**: CSV (simple, portable), Excel (manual editing, multi-sheet), JSON (nested structures, API payloads)

### 1.8 Exploratory Data Analysis (EDA)
- **Why it matters**: Understand structure, detect issues early, generate hypotheses, reduce modeling mistakes
- **Checklist**:
  - Shape and schema: rows, columns, data types
  - Missing values: NaN or placeholders (?, -)
  - Summary statistics: mean, mode, min/max, quartiles
  - Distributions: how data is spread
  - Outliers and anomalies: unusual data points
- **Descriptive statistics**: Extreme ranges impact model stability; skewed targets affect error interpretation; unusual quartiles hint at caps or collection limits

### 1.9 pandas DataFrame
- Rows = observations, Columns = features, Index = row label
- `df.shape` → (rows, columns)
- `df.dtypes` → data type of each column
- `df.head()` → first 5 rows
- `df.info()` → shape + types + non-null counts

### 1.10 ML Starter's Toolkit
- **Python**: primary language
- **pandas**: tabular data manipulation
- **NumPy**: arrays and mathematical operations
- **scikit-learn**: ML models
- **Google Colab**: cloud-based notebooks for experimentation
- **Notebooks vs Scripts**: Notebook = exploratory, iterative, visual; Script = repeatable, versionable, production-friendly

---

## WEEK 2: PREPROCESSING, ENCODING, SCALING, & TOOLING

### 2.1 Missing Values Handling
- **What are missing values**: NaN (not recorded, not applicable, unknown) or placeholders (?, -)
- **Strategies**:
  1. Drop column (if >50% missing or low signal)
  2. Drop row (if very few rows affected and column critical)
  3. Fill with mean or median (numeric, no strong meaning)
  4. Fill with mode (categorical, no strong meaning)
  5. Fill with constant ("None", 0, "Unknown")
  6. Forward/backward fill (time series only)
- **Rules of thumb**: >50% missing → consider dropping; null by design → fill with "None" or 0; genuinely missing → median/mode; **always impute using train statistics only**

### 2.2 Categorical Encoding
- **Why models need numbers**: Most algorithms use matrix operations; "Neighborhood = OldTown" is meaningless to math formula
- **Label Encoding**: Each category gets a number (0, 1, 2...) – preserves ordinal relationships
- **One-Hot Encoding**: Each category becomes a binary column – creates new columns
- **Ordinal vs Nominal**:
  - Ordinal: meaningful order (quality ratings, size buckets) – order of encoding matters
  - Nominal: no meaningful order (color, neighborhood) – order doesn't matter
  - Wrong choice causes models to learn incorrect relationships
- **Cardinality Problem**: High cardinality (many unique values) creates too many columns; solutions include grouping rare categories, dropping, or target encoding

### 2.3 Feature Scaling
- **Why scaling matters**: Algorithms using distances or gradients treat large-scale features as more important
- **Example**: LotArea (1,300–215,000) vs OverallQual (1–10) – LotArea dominates without scaling
- **Three Scalers**:
  - **StandardScaler**: subtract mean, divide by std → result: mean=0, std=1 (sensitive to outliers)
  - **MinMaxScaler**: compress to [0,1] range (very sensitive to outliers)
  - **RobustScaler**: uses median and IQR (robust to outliers, use when outliers present)

### 2.4 Feature Pipelines (sklearn.pipeline)
- **Problem with manual preprocessing**: Hard to reproduce, easy to apply in wrong order, hard to share, execution order not guaranteed
- **Pipeline**: Chain of (name, transform) steps; each step's output feeds the next; last step can be a model
- **Guarantees**: Correct order, fit-on-train-only, single save
- **ColumnTransformer**: Apply different transformations to different column groups (numeric vs categorical)

### 2.5 Data Splitting & Validation
- **Train/Test Split**: 70-90% train, 30-10% test
- **Train/Validation/Test Split (Three-Way)**: 60/20/20 – train learns, validation tunes (used many times), test evaluates once at end
- **Methods**: `train_test_split` (simple, set random_state for reproducibility), `StratifiedShuffleSplit` (for imbalanced classification)
- **Features (X) vs Target (y)**: No leakage between X and y
- **Validation Set as Decision Budget**: Every model comparison uses validation set; test set used once at very end

### 2.6 Regression Models
- **Linear Regression**: Baseline, fits best straight line, fast, interpretable, assumes linearity
- **Decision Trees**: Tree-structured, splits on one feature at a time; deep trees = overfit (high variance), shallow trees = underfit (high bias)
- **Random Forest**: Ensemble of trees, handles non-linearity, robust to outliers
- **Gradient Boosting**: Trains sequentially, learns from previous errors, often best accuracy

### 2.7 Regression Metrics
- **MAE (Mean Absolute Error)**: Same unit as target, stable, easy to explain
- **MSE (Mean Squared Error)**: Punishes large misses heavily, units are squared
- **RMSE (Root Mean Squared Error)**: Target units, sensitive to outliers
- **R-squared**: Variance explained vs predicting mean (can be negative on new data)
- **Best practice**: Always report 2+ metrics

### 2.8 Model Workflow & Deployment
- `fit(X_train, y_train)` → `predict(X_test)` → compare predictions with truth
- `joblib.dump(model, path)` and `joblib.load(path)` for saving/loading models
- **Why save**: Reproducibility and deployment

### 2.9 Prompt Engineering (Complete)
- **Definition**: The art and science of communicating intent to AI models
- **Three principles**: Clarity > Cleverness, Context is Everything, Iterate Don't Guess

**Techniques:**
- **Zero-Shot**: Ask directly with no examples – be specific about task, format, constraints
- **Few-Shot**: Provide input/output examples so model learns pattern – cover ALL categories, include edge cases
- **Chain-of-Thought (CoT)**: "Think step by step" – improves math, logic, analysis; can be simple or structured with defined reasoning steps
- **Role/Persona**: Tell model who to be – shapes tone, vocabulary, depth, perspective
- **System vs User**: System = persistent rules (employee handbook), User = per-turn request (customer walking in)
- **Structured Output**: Specify exact format (JSON, XML, tables, CSV) – show the schema
- **Prompt Chaining**: Break complex tasks into sequence; output of one feeds the next
- **Temperature**: Low (0-0.3) = focused, deterministic; High (0.7-1.0) = creative, varied
- **Delimiters**: Use markers (triple quotes, XML tags, dashes) to separate instructions from data
- **Negative Prompting**: Tell model what to AVOID; combine positive + negative for best results

**Prompt Injection & Defense:**
- **What it is**: Untrusted input hijacks model behavior (analogous to SQL injection for LLMs)
- **Three defense layers**:
  1. Delimiters: wrap untrusted content in boundaries + explicit instruction to ignore embedded commands
  2. System/User Split: keep instructions in system prompt (higher priority)
  3. Output Validation: check response format before showing to user
- **Rule of thumb**: Never trust user input – always assume adversarial

**ReAct-Style Agents:**
- Pattern: Reasoning → Action → Observation → Reasoning (loop)
- Format: Thought → Action: search("[query]") → Observation → Final Answer
- Critical: "Never fabricate Observation" – prevents hallucination

### 2.10 LLMs & Hosted Models
- **How LLMs work**: Trained on massive text → learns patterns → you give prompt → predicts next words
- **Key insight**: LLMs don't "understand" – they predict; they can hallucinate (confident but wrong)
- **Terminology**: Token (~¾ word), Context Window (max tokens), Temperature (randomness), Hallucination, Fine-tuning
- **Transformer Architecture (2017)**: Self-attention (words matter to each other), parallel processing (reads all at once), massive scale (billions of parameters)
- **Hosted vs Local**: Hosted = API access, state-of-the-art, costs money, data leaves machine; Local = download, free, private, offline, needs GPU
- **Major providers**: OpenAI (GPT-4o), Anthropic (Claude), Google (Gemini), Open-source hosted (Llama, Mistral, DeepSeek)

### 2.11 AWS Services
- **S3 (Simple Storage Service)**: Stores files, any size, event-driven
- **Lambda**: Runs code without servers, event-driven, stateless
- **Bedrock**: Foundation models via API (Claude, Llama, Mistral) – pay per token
- **Polly**: Text-to-speech, natural voices, MP3/OGG output
- **SES (Simple Email Service)**: Send emails programmatically, attachments, HTML
- **Use case**: Research paper PDF uploaded to S3 → Lambda triggers → Bedrock summarizes + Polly narrates → SES sends email digest

### 2.12 Docker
- **What it is**: Packages application + dependencies into container – "Package once, run anywhere"
- **Key concepts**: Image (read-only blueprint, like class), Container (running instance, like object), Dockerfile (recipe)
- **Commands**: `docker pull`, `docker build -t`, `docker run -p`, `docker ps`, `docker stop`, `docker images`
- **Dockerfile**: FROM (base image), WORKDIR (working directory), COPY, RUN, EXPOSE, CMD
- **Docker Compose**: Define multi-container apps with YAML; `docker compose up` starts everything

---

## WEEK 3: FEATURE ENGINEERING, SELECTION & VISUALIZATION

### 3.1 Feature Engineering
- **Definition**: Transforming raw facts into better predictive signals – not adding new data, reshaping what you have
- **"Better data beats better algorithms"** – Kaggle winners spend 70-80% of time on feature engineering
- **Four types**:
  1. **Domain features**: Combine columns using real-world knowledge (TotalSF = 1stFlrSF + 2ndFlrSF + TotalBsmtSF)
  2. **Temporal features**: Compute elapsed time (HouseAge = YrSold - YearBuilt)
  3. **Interaction features**: Multiply columns for joint effects (QualArea = OverallQual × GrLivArea)
  4. **Mathematical transforms**: Change distribution (log1p on LotArea for right-skewed data)
- **Binary indicators**: Convert sparse numeric columns to presence/absence (HasPool, HasFireplace, HasGarage)
- **Leakage boundary**: Safe = features known at inference time; Unsafe = using target variable or full dataset before splitting
- **Three rules**: Always validate with val RMSE, never leak, stop when last 3 features gave <1% improvement

### 3.2 Feature Selection
- **Why it matters**: Noise features add variance without bias reduction; correlated features split model weight (multicollinearity); computational cost; overfitting risk
- **The Curse of Dimensionality**: In 100D, 100 points are isolated → nearest neighbors not nearby; distance/density concepts break down
- **Selection methods**:
  - **Variance Threshold**: removes near-zero variance features (fast, no model)
  - **Correlation Filter**: drop one from any pair with |r| > 0.90 (fast, no model)
  - **RFE (Recursive Feature Elimination)**: trains model repeatedly, removes weakest (slow, uses model)
  - **Tree Importance**: feature importance from trained tree model (fast, one fit, uses model)
- **Risk of over-selecting**: Too few features = underfit; always validate with val RMSE before and after

### 3.3 Visualizing Representations (PCA & t-SNE)
- **The high-dimensional space problem**: Ames has ~200 dimensions; humans perceive up to 3 dimensions
- **PCA (Principal Component Analysis)**:
  - Finds axes of maximum variance (linear combination of original features)
  - PC1 captures most variance, PC2 orthogonal next most
  - Requires StandardScaler before PCA
  - Linear only, components not interpretable as single concepts
  - Variance explained: 1 component = ~35%, 2 = ~50%, 5 = ~65%, 20 = ~82%, 50 = ~91%
- **t-SNE (t-distributed Stochastic Neighbor Embedding)**:
  - Preserves local neighborhood structure (which points are nearest neighbors)
  - Finds dense subgroups (quality tiers, neighborhood clusters)
  - Slower, non-deterministic, not for modeling
- **PCA vs t-SNE**: PCA fast and deterministic (seconds), preserves global structure, use for modeling; t-SNE slow and non-deterministic (minutes), preserves local clusters, not for modeling

### 3.4 Comparing Representations
- **Experimental design**: Raw (249 features) vs +Engineered (~260) vs +Selected (~160) vs PCA-50 (50 components)
- **Evaluation protocol**: Fit on X_train → evaluate on X_val → record val RMSE and R² → record train RMSE (monitor gap) → select best on val RMSE → evaluate winner on X_test once
- **Key lessons**:
  - Engineered > Raw: domain features added signal model couldn't recover
  - Selected ≈ Engineered: selection removed noise but tree model already robust
  - PCA < Raw: compression loses signal for tree models
  - The right representation depends on the model family

---

## WEEK 4: CLASSIFICATION, RAG & AGENTIC AI

### 4.1 Classification Essentials
- **From regression to classification**: Continuous number → category/label; MSE/RMSE → Log loss/cross-entropy; single number → probability per class
- **Classification metrics**:
  - **Confusion Matrix**: TP (correctly predicted churn), TN (correctly predicted no churn), FP (wasted intervention), FN (missed opportunity)
  - **Precision** = TP/(TP+FP): "Of all predicted churners, how many actually churned?"
  - **Recall** = TP/(TP+FN): "Of all actual churners, how many did we catch?"
  - **F1** = 2 × (Precision × Recall)/(Precision + Recall): harmonic mean
  - **Accuracy** = (TP+TN)/Total: misleading with imbalanced classes
  - **ROC/AUC**: probability model ranks positive above negative; 0.5 = random, 1.0 = perfect
- **Class imbalance**: Telco has 73.5% No Churn / 26.5% Churn; strategies: `class_weight='balanced'`, threshold adjustment, SMOTE
- **Calibration**: Well-calibrated = predicted probability ≈ actual proportion; transformers tend to be overconfident
- **Threshold analysis**: Default 0.5; lower (0.3) = higher recall, more false alarms; higher (0.7) = higher precision, miss more churners

### 4.2 Hyperparameter Tuning
- **Parameters vs Hyperparameters**: Parameters learned from data during training; hyperparameters chosen before training
- **GridSearchCV**: Exhaustive, tries every combination – best for small search spaces (<20 configs)
- **RandomizedSearchCV**: Tries random configurations – better for large spaces
- **StratifiedKFold**: Ensures each fold maintains same class ratio – prevents validation set leakage
- **Key GradientBoosting hyperparameters**: n_estimators (100-500), learning_rate (0.01-0.2), max_depth (2-6), min_samples_leaf (1-20), subsample (0.7-1.0)
- **Scoring metrics for tuning**: roc_auc (ranking), f1 (default for imbalanced), recall (maximize catching), precision (minimize false alarms)

### 4.3 Experiment Tracking & Reproducibility (MLflow)
- **What to log**: Model class and ALL hyperparameters, train/val/test split config, preprocessing config, evaluation metrics, date/time, library versions, dataset hash
- **MLflow**: Open-source platform; Experiment = named collection of runs; Run = single execution with params, metrics, artifacts
- **Reproducibility checklist**:
  1. `random_state=42` on all random operations
  2. `numpy.random.seed(42)` at top of notebook
  3. Log library versions
  4. Log dataset filename, row count, column count, md5 hash
  5. Log all hyperparameters
  6. Save model with `joblib.dump`
  7. Notebook runs cleanly from top to bottom

### 4.4 RAG (Retrieval-Augmented Generation) – Foundation

**The Problem:**
- LLMs hallucinate when they don't know the answer
- Context windows are limited
- Every token costs money
- More text = worse answers

**The Solution (Grounding):**
- Paste real context into prompt before asking question
- But can't paste everything → need retrieval

**The RAG Loop (3 Steps):**
1. **Retrieve**: find relevant chunks from knowledge base
2. **Augment**: build prompt with context + question
3. **Generate**: LLM answers based ONLY on retrieved context

**Loading & Chunking:**
- Loading: convert many formats to plain text
- **Chunking strategies**:
  - Fixed-size with overlap: simple, works on any text, may cut mid-sentence
  - Section-based: chunks match meaning, needs structured documents
- **Chunk size tradeoff**: too small = missing context, too large = irrelevant info

**Embeddings & Vector Stores:**
- **Embedding**: coordinate for meaning – fixed-length vector where similar ideas are near each other; distance = similarity; learned from billions of sentences
- **Why semantic search beats keyword**: "annual leave policy" vs "Employees get 20 vacation days" – no keyword match, but semantic match works
- **Vector Store (ChromaDB)**: Stores embeddings + metadata; `POST /ingest` (chunks → embeddings → store), `POST /search` (query → top-k chunks with distances)
- **Metadata**: source file, chunk ID, filters for debugging

**The RAG Prompt:**
- **Strict (Grounded)** : "Answer only from the context below. If the answer isn't there, say 'I don't know.' Cite your sources."
- **Loose**: "Here's some context and a question – answer it."

**Source Attribution:**
- Always return sources – enables trust, debugging, compliance

**RAG vs Plain LLM:**
- "How many vacation days?" → Plain: "15 days" (made up); RAG: "20 days" with source
- "Capital of France?" → Plain: "Paris" (from training); RAG: "I don't know" (not in docs)

**RAG Failure Modes:**
- **Confidence scoring (4 levels)** : High (0.8-1.0): strong match; Medium (0.6-0.8): reasonable; Low (0.4-0.6): weak, verify; None (<0.4): no relevant content
- **Refusing to answer is a feature**: When top scores below threshold → stop before LLM invents something – faster, cheaper, more honest
- **Questions RAG struggles with**: subjective, temporal, cross-domain synthesis, world knowledge (already in LLM)
- **Transparency**: UI shows confidence badge, sources, debug info; embedding visualization shows clusters

### 4.5 Agentic AI – Complete

**What is an Agent?**
- An LLM that can decide which actions to take
- LLM alone: generates text only
- LLM + Tools = Agent: generates text AND takes action

**Session 1: Tool Calling**
- **How it works**:
  1. Code sends prompt + tool schemas (JSON Schema)
  2. LLM returns a tool call (structured request, never executes)
  3. Your code executes the tool
  4. Result returned to LLM
- **Tool Schema fields**: name (identifier), description (MOST important – LLM reads to decide), parameters (JSON Schema), required (args that must be provided)
- **Tool Registry pattern**: single dict mapping tool name → schema + executor; single source of truth, easy to extend, easy to gate
- **Security**: validate everything, treat LLM output as untrusted input

**Session 2: Agent Loop (ReAct)**
- **The ReAct pattern**: Reasoning → Action → Observation → Reasoning (loop)
- **Agent loop code (~20 lines)** :
```python
for step in range(max_steps):
    response = call_llm_with_tools(messages, tools)
    if response["finish_reason"] == "stop":
        return answer
    for tool_call in response["tool_calls"]:
        result = execute_tool(tool_call)
        messages.append(tool_result_message(tool_call, result))
```
- **Critical components**: messages = agent's memory; max_steps = safety cap (default 10); finish_reason = "stop" when LLM done
- **Why agents loop forever**: tool result not appended, LLM never decides it has enough, tool returns empty/error, two tools that re-trigger each other
- **Read vs Write tools**: Read = safe (calculator, search, clock) always allowed; Write = dangerous (task creation, file write) need gates

**Session 3: Safety & Control (LangGraph)**
- **LangGraph vs Manual**: 5 lines vs 50 lines; automatic state management; built-in checkpointing (persistence across restarts); streaming; HITL
- **LangGraph ReAct Agent**:
```python
agent = create_react_agent(model, tools, checkpointer=MemorySaver())
result = agent.invoke({"messages": [("user", goal)]},
                      config={"configurable": {"thread_id": "1"}})
```
- **Why thread_id matters**: same ID = same conversation (memory across restarts)
- **Injection Detection (regex patterns)** : "ignore all previous instructions", "you are now a...", "forget all your rules", "pretend you are unrestricted", "system:"
- **Defense in Depth (4 layers)** :
  1. Input sanitization (cheapest, catches noise)
  2. Injection detection (regex/ML on prompt)
  3. Tool permissions (whitelist per request)
  4. Human-in-the-loop (manual approval for writes)
- **Human-in-the-Loop (HITL)** : pause before write operations, human approves/denies; required for deletions, payments, emails

**Session 4: Orchestration & Observability**
- **Multi-Agent Systems**: Complex goals overwhelm single agent; specialized agents collaborate better
- **Planner-Executor Pattern**: Planner breaks goal into steps (1-5), no tool access, uses Pydantic structured output; Executor runs each step with tools; Safety layer checks everything
- **Tracing (Observability)** : Structured log of every step with timing; total duration, step durations, tool outputs, status; "You can't debug what you can't see"

---

## WEEK 5: MLOPS & PRODUCTION PATTERNS

### 5.1 Model Artifacts & Versioning
- **Model artifact**: folder containing model pickle + preprocessing pipeline + metadata – "All three or none"
- **Model registry**: Run → Registered Model → Version → Stage (Staging, Production, Archived)
- **MLflow registry mechanics**:
```python
mlflow.sklearn.log_model(pipeline, artifact_path="model",
                         signature=signature, registered_model_name="model")
client.transition_model_version_stage(name, version, stage="Staging")
loaded = mlflow.sklearn.load_model("models:/model/Staging")
```
- **Semantic versioning for ML**: v0.1.0 (initial), v0.1.1 (patch, ≤0.5% metric delta), v0.2.0 (minor, new hyperparameters/features), v1.0.0 (major, input schema changed)
- **One staging version rule**: assert only ONE model version in Staging – "If two models are in Staging, you have a bug, not a backup"

### 5.2 Input Validation & Robust Inference
- **Why validation matters**: The world sends garbage – missing fields, wrong types, unknown categorical values; all three pass silently if you let them
- **Pydantic v2**:
```python
class TelcoChurnRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    Contract: Literal['Month-to-month', 'One year', 'Two year']
    tenure: int = Field(ge=0, le=100)
```
- **Closed enums via Literal**: If not in list, not a request – validation fails loudly
- **Layered defense**: Outer = Pydantic rejects loudly with validation_error; Inner = OneHotEncoder(handle_unknown='ignore') silently zero-encodes
- **Threshold tuning as cost decision**: Telco churn = cost(FN) >> cost(FP) → bias recall; fraud detection = cost(FP) >> cost(FN) → bias precision

### 5.3 Observability – Local vs Production
- **The iceberg problem**: Local works, production breaks
- **Structured logs vs print**: print is unstructured and unqueryable; structured logs have request_id, model_version, latency_ms, prob, threshold, warning
- **The Four Golden Signals**:
  - **Latency**: how fast (p50, p95, p99)
  - **Errors**: how often it breaks (validation_error/min, model_error/min)
  - **Traffic**: how much it serves (requests/min)
  - **Saturation**: how full the box is (CPU%, memory%, queue depth)
- **PSI (Population Stability Index)** for numerics: PSI = Σ(p_cur - p_ref)·ln(p_cur/p_ref); thresholds: <0.10 OK, <0.20 WATCH, <0.25 ALERT, ≥0.25 ALARM
- **Chi-square for categoricals**: scipy.stats.chisquare(observed, expected); p < 0.01 triggers ALERT
- **Drift ≠ Accuracy Loss**: Drift detection asks "has the world shifted?"; Accuracy asks "is model still right?"; both can fire independently
- **Alert rules in code**: check PSI values ≥0.20, label drift ≥5pp, p99 latency >200ms → return reasons list

### 5.4 End-to-End Production Pipeline
- **The production pipeline flow**: JSON request → Pydantic validate → predict_proba → log + drift buffer → JSON response
- **Two response shapes**:
  - **Success**: ok=True, request_id, model_version, threshold, churn_probability, churn_label, latency_ms, warning
  - **Error**: ok=False, request_id, error, details, latency_ms
- **Three failure paths**:
  1. Bad JSON → invalid_json (microseconds)
  2. Bad shape (missing field, wrong type, unknown enum) → validation_error (microseconds)
  3. Model crash (predict_proba raised) → model_error (logs traceback, recovers)
- **The serve() function pattern**: try-catch for each failure type, rolling window for drift detection, warning included in success response

### 5.5 Queues with Redis

**The Problem:**
- Slow tools block the request (30-second scrape holds HTTP connection)
- Bursts kill you (ten users at once → ten parallel scrapes → memory blows up)
- Crashes lose work (app dies mid-scrape → work is gone → user retries)

**The Solution: Decouple Request from Work**
- Return job_id instantly; workers consume jobs at their own pace; users poll for result

**Four Components:**
- **Producer**: submits jobs, knows the what (app/queue/client.py)
- **Broker**: holds queued jobs, hands them out (Redis via arq)
- **Consumer/Worker**: pulls jobs, runs them, reports results (app/workers/runner.py)
- **Result store**: finished work so producer can read it (app/queue/results.py)

**Delivery Guarantees:**
- **At-most-once**: ≤1 delivery – losing job preferable to running twice
- **At-least-once**: ≥1 delivery – default; pair with idempotency
- **Exactly-once**: the myth – can't be guaranteed across distributed systems
- **Production answer**: at-least-once + idempotent tasks = exactly-once effects

**Idempotency:**
- **Definition**: Running twice with same input produces same effect as running once
- **Examples**: SET user.email = "x" (idempotent), INCREMENT view_count (not idempotent), UPSERT (idempotent), INSERT INTO charges (not idempotent)
- **CP4 two-layer defense**:
  1. Producer-side: check if result already exists
  2. Broker-side: arq refuses second job with same job_id while first is queued/running

**Retries: Transient vs Permanent:**
- **Transient** (5xx, 429, network timeout, connection reset): retry with exponential backoff + jitter (1s, 2s, 4s, 8s)
- **Permanent** (4xx, validation error, schema mismatch): fail fast → send to DLQ

**Dead Letter Queue (DLQ):**
- **Wrong answer**: silently drop job (missing job, no idea it was missing)
- **Right answer**: send dead jobs to DLQ – separate Redis list for inspection
- **When job dies permanently**: write tombstone, push to DLQ list, fire webhook, log warning
- **Rule**: never let a job vanish – either it succeeds, or tombstone is visible somewhere

**Job Lifecycle (5 states)**: QUEUED → RUNNING → COMPLETED; on exception → transient? retry → permanent? DEAD_LETTER

**Worker Scaling**: `docker compose up -d --scale worker=4` – same code, multiple processes

**Lease/Visibility Timeout**: Broker gives worker a lease (default 30s); miss deadline → broker assumes worker crashed and redelivers

### 5.6 MCP (Model Context Protocol)
- **The problem MCP solves**: Without MCP, each tool requires glue code (schema + function + wiring) from scratch
- **MCP = USB-C for AI agents**: one standard plug so any agent can use any tool
- **API vs MCP**: API = one specific door (each has own URL, params, auth, response format); MCP = universal plug (every server speaks same protocol)
- **What an MCP server does**:
  - Discovery: Agent asks "what can you do?"; Server replies with available tools
  - Execution: Agent calls tool with inputs; Server returns results
- **MCP does NOT replace APIs** – MCP wraps them; your agent only learns ONE shape (MCP)
- **When to use**: building AI agent = default choice; reusable tools across agents = built for this

### 5.7 MCP vs A2A (Agent-to-Agent)
- **MCP**: connects agent to tools and data; vertical relationship (agent → tool); other side is dumb (just executes); answers "How do I give my agent capabilities?"
- **A2A**: connects agent to other agents; horizontal relationship (agent ↔ agent); other side is smart (reasons and plans); answers "How do I let my agent collaborate?"
- **A2A core ideas**: Agent Cards (manifest describing skills), peer-to-peer (discover and call over HTTP), task lifecycles (streaming, multi-turn, auth)
- **They work together**: Supervisor uses A2A to talk to Researcher; Researcher uses MCP to talk to Web search + Vector DB

### 5.8 Agents as Production Software (Week 5 – 4 Sessions)

**The mental model**: Agents are software systems. Architect them. Persist them. Test them. Operate them.

**The four upgrades:**
1. **Multi-Agent Architectures**: choose topology, handoffs, LangGraph Studio
2. **Memory & Persistence**: checkpoints, resumable workflows, survive restarts
3. **Agent Software Engineering**: tests, reproducibility, prompt versioning
4. **Long-Running Tools**: queues, workers, idempotency, retries, DLQ

**When to split (multi-agent):**
- Distinct skills, different tool sets per role, different prompts that conflict, want one agent to critique another
- **Don't split when**: one agent + better prompt would do, sub-tasks share context, latency budget tight, splitting just to look sophisticated

**Three topologies:**
- **Supervisor**: central agent decides which specialist to call – easy to debug
- **Hierarchical**: teams of teams – top-level supervisor delegates to sub-supervisors
- **Swarm/Handoff**: peer agents transfer control based on context – flexible, harder to control

**LangGraph primitives (3)** :
- **STATE**: typed dict that flows through graph – every node reads and updates
- **NODES**: async functions that take state and return Command (what to update, where to go next)
- **EDGES**: routes between nodes; conditional edges let graph branch on state

**Memory & Persistence:**
- **Short-term**: within single run, stored in graph state via Redis checkpointer
- **Long-term**: across sessions/users, stored in Postgres
- **Checkpointing**: save state at every node; resume anywhere; time-travel when something breaks
- **thread_id is everything**: same thread_id = same conversation (memory across restarts)

**Agent Software Engineering (4 practices)** :
1. **Test**: unit + integration, deterministic mocks, snapshot tests for trajectories
2. **Debug**: trace → replay → fix – reproduce failure, fix with confidence
3. **Version**: prompts and models in source control – pinned, reviewed, rolled back
4. **Reproduce**: seeds, deterministic mocks, snapshots – every run reproducible

**Mocking the LLM (non-negotiable)** : Replace chat model with fake at fixture level; return canned responses; tests run in milliseconds, $0, 100% reproducible

**Snapshots**: capture sequence of nodes visited; compare to 'golden' trajectory; fail if agent took weird path

**Tests vs Evals**: Tests = deterministic, fast, every commit, check structure; Evals = probabilistic, slow, nightly, measure quality

---

## WEEK 6: DEEP LEARNING & COMPUTER VISION

### 6.1 Deep Learning Fundamentals

**Why Deep Learning is "Worth Leaving" sklearn:**
- sklearn LogisticRegression: linear decision boundary, ~30 features
- Deep MLP/NN: non-linear, can fit images, scales to millions of features

**A Digital Neuron**: Inputs → weights → sum → activation → output

**Multi-Layer Perceptron (MLP)** : Input layer → hidden layer(s) → output layer

**Activation Functions:**
- **ReLU**: max(0,x) – most common for hidden layers
- **Sigmoid**: 1/(1+e^-x) – for binary classification output
- **Softmax**: for multi-class classification output
- **Tanh**: range [-1,1]

**Forward Pass:**
```python
Z1 = X @ W1 + b1           # (N, hidden_dim)
A1 = np.maximum(0, Z1)     # ReLU activation
Z2 = A1 @ W2 + b2           # (N, output_dim)
P = sigmoid(Z2)             # probability
```

**Loss Functions:**
- **Binary Cross-Entropy (BCE)** : for binary classification
- **Categorical Cross-Entropy (CCE)** : for multi-class classification
- **MSE**: for regression

**Backward Pass (Backpropagation)** : Chain rule applied to compute gradients; gradients flow from output back to input

**Stochastic Gradient Descent (SGD)** : Update rule: `W -= LR * dW`; mini-batch updates (not each sample, not full dataset)

**Training Loop:**
```python
for epoch in range(50):
    perm = np.random.permutation(N_train)
    for start in range(0, N_train, batch_size):
        idx = perm[start:start+batch_size]
        Xb, yb = X_train[idx], y_train[idx]
        _, cache = forward(Xb, W1, b1, W2, b2)
        dW1, db1, dW2, db2 = backward(cache, yb, W2)
        W1 -= LR * dW1; b1 -= LR * db1
        W2 -= LR * dW2; b2 -= LR * db2
```

**Three Sanity Checks:**
1. Loss starts at expected value (e.g., -log(0.5) for balanced binary)
2. Overfit a tiny subset (10 samples) → loss → 0
3. Train/val gap tells overfitting story

### 6.2 PyTorch Fundamentals

**nn.Module (The PyTorch Building Block)** :
```python
class TinyMLP(nn.Module):
    def __init__(self, input_dim=1024, hidden_dim=64, output_dim=1):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, output_dim)
    def forward(self, x):
        z1 = self.fc1(x)
        a1 = F.relu(z1)
        z2 = self.fc2(a1)
        return z2  # raw logits
```

**Byte-Identical Diagnostic**: Verify PyTorch implementation matches NumPy reference; max |Δ| < 1e-6 → correct

**From Binary to Multi-Class:**
- Output dim: 1 → 37
- Activation: Sigmoid → Softmax
- Loss: BCE → CrossEntropyLoss
- Prediction: threshold at 0.5 → argmax
- Random baseline: 0.50 → 0.027 (1/37)

**The PyTorch Training Stack:**
```python
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=30)

for epoch in range(EPOCHS):
    for xb, yb in train_loader:
        optimizer.zero_grad()
        loss = criterion(model(xb), yb)
        loss.backward()
        optimizer.step()
    scheduler.step()
```

**Why Adam Beats Plain SGD**: SGD = same LR for every parameter; Adam = per-parameter adaptive LR using moving averages of grad and grad² – default choice

**Early Stopping**: Track best validation loss; stop if no improvement for N epochs (e.g., 8); restore best weights at end

**Learning Rate Schedulers**: CosineAnnealingLR anneals from initial LR to ~0 over T_max epochs – prevents overshooting

### 6.3 CNNs and Image Pipelines

**Why an MLP Is Wasted on Images**: Pixel (0,0) and (1,0) are neighbors in 2D space; MLP treats them as independent dimensions; 1920×1080 image has 2,073,600 pixels → billions of parameters

**Convolution (The CNN Building Block)** : 3×3 kernel slides over image; 9 weights × 1 bias = 10 parameters (vs 1024 for fully connected); preserves spatial locality

**The PyTorch Image Pipeline:**
```python
train_tf = T.Compose([
    T.Resize(72), T.RandomCrop(64),
    T.RandomHorizontalFlip(p=0.5),
    T.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
    T.ToImage(), T.ToDtype(torch.float32, scale=True),
    T.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])
```

**Data Augmentation (Free Training Data)** : Flipped, color-jittered, cropped, rotated

**TinyCNN Architecture:**
```python
class TinyCNN(nn.Module):
    def __init__(self, n_classes=37):
        self.conv1 = nn.Conv2d(3, 32, 3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, 3, padding=1)
        self.conv3 = nn.Conv2d(64, 128, 3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)
        self.gap = nn.AdaptiveAvgPool2d(1)  # global average pooling
        self.fc = nn.Linear(128, n_classes)
        self.dropout = nn.Dropout(0.3)
```

**Global Average Pooling vs Flatten**: Flatten → large feature vector, many params; GAP → one value per channel → far fewer params

**Week 6 Progression:**
- Day 1: NumPy MLP, cat/dog binary → 0.676
- Day 2: PyTorch MLP, 37-class breed → 0.071
- Day 3: Small CNN + augmentation → 0.155
- Day 4: Pretrained ResNet → ~0.87

### 6.4 Transfer Learning, Detection & Segmentation

**Transfer Learning**: ImageNet (1.2M images, 18 layers) learns edges, textures, parts, anatomy; use those features, train only new classifier head

**Pretrained Weights API:**
```python
weights = ResNet18_Weights.IMAGENET1K_V1
model = resnet18(weights=weights)
preprocess = weights.transform()  # model's expected pipeline
```

**Linear Probe vs Full Fine-Tune:**
- **Linear Probe** (frozen backbone, train only head): trainable ~0.16%, low risk, lower ceiling
- **Full Fine-Tune** (everything trainable): trainable 100%, medium risk, highest ceiling

**Three Computer Vision Tasks:**
- **Classification**: single label per image ("cat")
- **Object Detection**: bounding boxes + labels ("cat at [x,y,w,h]") – model: Faster R-CNN
- **Segmentation**: pixel-level labels – model: DeepLabV3 (outputs mask per pixel)

**Key Takeaways for Computer Vision:**
1. Pretraining > everything else – fine-tune from pretrained backbone, always
2. The model's preprocessing is part of the model – use weights.transforms()
3. Detection and segmentation are inference-first – don't train from scratch unless you have to

---

## WEEK 7: NLP, TRANSFORMERS & ADVANCED RAG

### 7.1 Text Representations

**The Representation Problem**: Neural network needs fixed-length numeric vectors; text is variable-length string; representation = rule that turns string into vector

**Token types:**
- **Whitespace**: split on spaces ("hello world" → ["hello", "world"])
- **Subword**: split into frequent pieces ("running" → ["run", "##ning"])
- **Character**: every character ("hi" → ["h", "i"])

**Bag-of-Words (BoW)** : Document = multi-set of its tokens; order discarded; becomes sparse vector of length |vocab| with token counts

**TF-IDF**: Re-weights BoW – down-weight tokens that appear in many documents, up-weight rare ones
- TF = frequency of term in document
- IDF = log(total documents / documents containing term)
- TF-IDF = TF × IDF

**Subword Tokenization:**
- **BPE (Byte-Pair Encoding)** – GPT-2 style: merge most-frequent character pairs until vocab full
- **WordPiece** – BERT style: merge pair that maximizes corpus likelihood
- Both produce ~30k-50k token vocabs; gracefully degrade unknown words into known pieces

**Word Embeddings**: Pre-trained encoder maps each token/sentence to real vector (384-768 dimensions); trained so semantically similar inputs land near each other; cosine similarity approximates semantic similarity

**When BoW Wins vs When Embeddings Win:**
- **BoW/TF-IDF**: balanced classification, stable vocabulary, latency-critical (sub-ms), abundant labels
- **Embeddings**: paraphrase-heavy data, retrieval/search, low-data regimes, multi-task setups

### 7.2 Fine-Tuning Transformers

**The Two-Stage Paradigm**: Pretraining (language modeling on massive corpus) → Fine-tuning (adapt to specific task with small labeled dataset)

**What Gets Transferred**: Lower layers = general language understanding (syntax, grammar); higher layers = task-specific patterns

**Model Comparison (AG News)** :

| Model | Parameters | Fine-tune Time (T4) | Macro-F1 |
|-------|------------|---------------------|----------|
| DistilBERT | 66M | ~10 min | ~0.94 |
| BERT-base | 110M | ~20 min | ~0.945 |
| BERT-large | 340M | ~80 min | ~0.95 |

**Training Arguments (Canonical Defaults)** : learning_rate=2e-5, num_train_epochs=2-3, per_device_train_batch_size=16, warmup_ratio=0.1

**Artifacts (save_pretrained)** : config.json (architecture), model.safetensors (weights), tokenizer files, id2label/label2id (human-readable names)

**LoRA (Low-Rank Adaptation)** : Freeze base weights W; learn small matrices A ∈ R^(d×r) and B ∈ R^(r×d); target attention projections (~40M trainable out of 8B = 0.5%); compute gains 5-10×, storage gains 250× (artifact ~1 MB)

### 7.3 NLP Pipelines

**Three NLP Tasks:**

1. **NER (Named Entity Recognition)** : Extract entities (people, orgs, dates, locations); token-level labels; BERT-based model

2. **Zero-Shot Classification**: Uses NLI (Natural Language Inference) – "Does this text entail this label?"; flexible (label set changes without retraining); slower, less accurate than fine-tuned

3. **Summarization**:
   - **Extractive**: pick existing sentences – faithful, fast, static
   - **Abstractive**: generate new sentences – fluent, can synthesize, can hallucinate
   - Modern summarizers (BART, T5, Pegasus) are abstractive

**ROUGE Metric**: Measures n-gram overlap between generated and reference summary; cheap, reproducible, industry standard; weaknesses: rewards extractive copying, blind to negation, doesn't measure faithfulness

**Pipelines as Composable Pieces**: Each pipeline() is callable: text → JSON-serializable dict; chain multiple into one analyze(text) → dict; dict is contract (JSON, easy to log, easy to ship, easy to version)

**Latency Profile:**
- Classification (DistilBERT, fine-tuned): 10-30 ms
- NER (BERT-base): 50-100 ms
- Zero-shot (BART-MNLI): 200-500 ms
- Summarization (DistilBART): 1500-3000 ms

**Production Patterns**: Sequential (today) → per-pipeline batching, async on slow stages, try/except per stage, timeouts (production)

### 7.4 Comparing ML vs DL vs LLM

**Week 7 Progression:**
- Day 1: TF-IDF + Logistic Regression → macro-F1 ~0.905
- Day 2: Fine-tuned DistilBERT → macro-F1 ~0.940
- Day 3: Zero-shot via NLI → macro-F1 ~0.800

**Five Axes That Decide Everything**: Accuracy, latency, cost, maintainability, data requirements

**Model Costs:**
- Classical ML: marginal ≈ 0, amortized tiny
- Deep Learning: marginal ~$0.05/1k, amortized modest
- LLM: marginal ~$0.10-1/1k, amortized zero (no training)

**Latency Percentiles:**
- **p50 (Median)** : typical user experience
- **p95**: worst-case for majority
- **p99**: common production SLA target
- **Mean (Average)** : often misleading – skewed by outliers

**Cascading Classifiers (Tiered System)** :
- Tier 1: TF-IDF + LR – all traffic, near $0, handles ~75% volume
- Tier 2: Fine-tuned DL – low confidence from Tier 1, higher cost, handles ~25%
- Tier 3: LLM zero-shot or human – uncertainty from Tier 2, highest cost, reserved for novel cases

**Confidence Calibration**: A 0.95 confidence prediction should be correct ~95% of the time; reality: fine-tuned transformers overconfident (0.95 score ≈ 85% correct); classical ML's softmax better calibrated

**When to Pick Different Approaches:**
- Latency-critical (<100ms, abundant labels) → fine-tuned DL
- Ultra-fast/stable (sub-ms, balanced classes, stable vocab) → classical ML
- Cold start/dynamic (no labels, low volume, label set changes weekly) → LLM zero-shot
- Efficiency at scale (high volume, mixed difficulty) → cascading

---

## WEEK 8: PRODUCTION DEEP DIVE

### 8.1 Multimodal Fundamentals

**The Multimodal Hypothesis**: There exist instances where P(y|image) ≈ 0.5 AND P(y|text) ≈ 0.5 BUT P(y|image,text) ≈ 1.0 – fusion only helps when interaction carries the signal

**Three Fusion Patterns:**
- **Early**: concatenate raw features before any encoder – rare (backbones expect native input)
- **Late**: run each encoder independently, average logits at end – cheap, parallel, no interaction
- **Intermediate (default)** : each encoder produces embedding, concatenate/attend over them – one small head predicts label

**What Goes Wrong with Naive Concatenation:**
- Head can't tell two sources apart
- Dominant modality causes head to ignore the other
- Larger image norms bias the head

**Making Fusion Robust – Modality Dropout**: During training, randomly zero out one branch's embedding (p=0.1) – never both at once; head learns to predict from one channel when other missing at serve time; reduces peak accuracy in exchange for graceful degradation

**Hateful Memes Dataset**: Facebook AI's ~10k memes, binary classification; adversarially constructed with confounders (same text/different image flips label, same image/different text flips label) – model using only image or only text cannot beat chance on confounder slices

### 8.2 Retraining, Shadow Scoring & Champion/Challenger Gate

**Shadow Scoring**: Champion (v1) serves traffic to users; Challenger (v2) receives same inputs, logs predictions, output NOT returned to users – zero user risk comparison

**The Naive Promotion Gate Is Wrong (3 ways)** :
1. Unpaired comparison ignores that v1 and v2 saw same rows
2. Aggregate lift hides per-segment regressions (Simpson's paradox)
3. Calibration can shift even when accuracy improves

**Paired Tests Beat Unpaired Tests**: For each row, compute v1 and v2 scores side-by-side; bootstrap-resample pairs → mean delta + 95% CI; same data, narrower CI

**Segment-Level Regression Check**: Define segments BEFORE experiment; for each segment, verify v2 non-inferior to v1

**Calibration Delta (The Silent Regressor)** : v2's natural calibration can differ even when ranking same; AUROC identical, cascade gates break silently; fit temperature scaling on both, compare |T_v2/T_v1 - 1| < 0.3

**Drift Trigger to Retrain**: PSI on embedding statistics > 0.2, OR 7-day flagged-rate drift > ε → fire retrain event; anti-flap guard: no second retrain within 72 hours

**Rollback as Code**: After promoting v2, monitor same metrics for 24-48 hours; if live AUROC delta regresses by > ε, auto-revert to v1; monitor is tripwire, silence is success

### 8.3 LLM Fine-tune and Deploy: LoRA, GGUF, Ollama

**The Fine-tuning Problem at LLM Scale**: Full fine-tune of Llama-3-8B requires ~80 GB GPU RAM; T4 has 15 GB → need parameter-efficient methods

**LoRA (Low-Rank Adaptation)** : Freeze base weights W; learn small matrices A ∈ R^(d×r) and B ∈ R^(r×d); target attention projections (~40M trainable out of 8B = 0.5%); inference uses W + (α/r)·B·A merged into single matrix

**4-bit Quantization & Unsloth**: Load base model in 4-bit (~5 GB for Llama-3-8B); Unsloth kernel speeds up training 2-5×

**Chat Template Discipline**: Llama-3 format: `<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|>`; always use `tokenizer.apply_chat_template()` – never hand-roll; mismatched tokenizer = silent garbage

**GGUF (GPT-Generated Unified Format)** : Portable inference format for llama.cpp, Ollama, LM Studio; single binary: quantized weights + tokenizer + chat template + metadata; exported from Unsloth with `model.save_pretrained_gguf()`; size after Q4_K_M: ~5 GB for Llama-3-8B

**Ollama**: Local LLM serving daemon; HTTP API on port 11434, OpenAI-compatible; commands: `ollama run my-model`; Modelfile = Dockerfile-shaped config (GGUF file, system prompt, chat template, parameters)

**Fine-tune-and-ship vs Hosted LLM:**

| Aspect | Fine-tune + Ollama | Hosted LLM |
|--------|-------------------|------------|
| Cost at low volume | One-time training + GPU host | Per-call (~$0.10-1/1k tokens) |
| Cost at high volume | Amortized toward zero | Linear |
| Accuracy on narrow domain | Wins | Loses without RAG |
| Latency | ~50-200ms | ~500-2000ms |
| Privacy | Data stays local | Data leaves network |

### 8.4 How to Be a Great AI Engineer

**What "AI Engineer" Actually Means:**
- **Applied ML Engineer**: ships ML systems – owns model, infrastructure, evaluation, MLOps
- **ML Infrastructure Engineer**: builds training, serving, feature systems
- **Research Engineer**: sits between research and production – pipeline from paper to running system

**The Five Sub-roles:**
- ML Engineer (MLE) – trains, evaluates, ships models
- AI/LLM Engineer – wires prompts, retrieval, tools, evals
- Data Scientist – investigates, runs experiments, builds dashboards
- ML Platform/Infrastructure Engineer – builds training/serving systems
- AI Product Engineer – owns user-facing feature with model inside

**Three Career Arcs:**
- **Depth arc**: world-class at one narrow thing – pay tops out high, mobility harder
- **Breadth arc**: any AI problem from idea to production – steady pay, excellent mobility
- **Product arc**: ML-aware product or engineering management – undervalued path

**The CV That Gets Read:**
- Lead with outcomes, not technologies ("Reduced inference latency by 60%")
- Include concrete numbers in every bullet
- Strict page limits (1 page junior, 2 max senior)
- Provide one live link a stranger can run in 5 minutes

**The Interview Loop:**
- Technical phone screen (30-90 min): ML concepts, production readiness
- System design (45-90 min): data flow, not just models
- Take-home (4-12 hours): working baseline + great README
- Behavioural (30-60 min): three deep, real-world stories

**What Great Engineers Do Better:**
- Write before building (one-page design doc)
- Define non-scope explicitly
- Invest in tooling (automate repetitive tasks)
- Read more than write (senior engineer's secret – having read 100× more code)
- Flag bad news early (Day 1 vs Day 5)

**The New Craft Skill (AI-Assisted Development)** : AI-assisted dev (Cursor, Claude Code, Copilot) is table stakes; the trap = shipping code you cannot debug; pattern that works = agent drafts, you read every line, delete what you don't understand; **your edge in 2026: "I can read what the agent wrote and find the bug it hid"**

**Building a Public Footprint**: Write now, not when senior (seniors have no time); personal blog with 5-10 deep posts > 100 LinkedIn updates; what works = project write-ups with runnable artifacts, honest post-mortems; what kills credibility = AI-generated posts, motivational rephrasing, daily engagement bait

**Three Habits That Compound:**
1. Ship one thing publicly every month (repo, post, demo)
2. Maintain one weak tie outside your company (talk monthly)
3. Spend 1-2 hours/week on something you are bad at

---

## WEEK 8 – ADVANCED PRODUCTION PATTERNS (Continued)

### 8.5 State & Correctness: Transactions, Outbox, Idempotency

**Three Things to Internalize:**
1. Make writes atomic – related writes commit together or not at all
2. Never dual-write – two systems with no shared transaction will disagree
3. Assume it arrives twice – at-least-once is default, design for duplicates

**Transactions as Correctness**: All-or-nothing guarantee – every write inside happens or none do; bank transfer example: debit A + credit B in one transaction; race condition fix: use `UPDATE balance = balance + 1` (atomic) instead of SELECT then UPDATE

**The Dual-Write Trap:**
```python
# BAD – crash between DB commit and publish
with conn.transaction():
    orders.insert(order)  # committed to Postgres
publish("order.created", order)  # crash HERE → DB has order, queue never heard
```
**Cannot reorder your way out** – both orderings have a failure window

**The Outbox Pattern:**
```python
# GOOD – event committed atomically with data
with conn.transaction():
    orders.insert(order)
    outbox.insert(topic="order.created", payload=order.json())
# Separate relayer drains table after, at-least-once
```
One transaction covers data + intent to publish; queue can be down – event safe in Postgres

**The Catch: At-Least-Once**: Relayer crashes after publish but before mark_published → republishes on restart; duplicates guaranteed by design; we chose "never lost" over "never repeated"

**Idempotency: Make Duplicates a No-Op:**
```python
def handle(event):
    if processed.exists(event.id):  # dedupe table
        return
    with conn.transaction():
        fulfill(event)
        processed.insert(event.id)  # same transaction
```
Dedupe insert and work share one transaction; without this, republished event charges/ships twice

**You Need Both**: Outbox alone → reliable duplicates; Idempotency alone → reliable data loss; Outbox + Idempotency = never lost + harmless repeats

### 8.6 Guardrails for LLMs with NeMo Guardrails

**The Problem – LLM with no guardrails**: Jailbreaks & injection ("Ignore your instructions" – and it complies); data leaks (spits out secrets, PII); hallucination (invents facts); off-topic/brand risk (medical or legal advice)

**What is NeMo Guardrails?**: NVIDIA open-source toolkit for programmable safety and control layers; sits between user and LLM – screens both directions; rules live in config, not buried in code; model-agnostic

**Five Kinds of Rails:**
- **Input rails** (focus today): screen user message before LLM
- **Dialog rails**: steer conversation along allowed paths
- **Retrieval rails** (focus today): screen retrieved context (RAG chunks)
- **Output rails** (focus today): screen LLM response before user sees
- **Execution rails**: guard tool/action calls

**How a Request Flows**: User → Input Rail → Retrieval Rail → LLM → Output Rail → Reply (any rail can short-circuit – LLM may never be called)

**Anatomy of a Guardrails Config:**
```
config/
├── config.yml      # which models + which rails active
├── prompts.yml     # prompts for self-check rails
└── rails/*.co      # Colang flows (custom rails)
```

**Input Rails**: Triggered the moment user message arrives; catches jailbreaks, off-topic, PII, toxic/abusive; activate with `rails.input.flows: [self check input, jailbreak detection heuristics]`; `self check input` = LLM call asking "does this break policy?"; blocked message returns configurable refusal (LLM never called)

**Output Rails**: Triggered after LLM responds – last line of defense; activate with `rails.output.flows: [self check output, self check facts, mask sensitive data on output]`; `self check facts` = grounded in retrieved context?; PII masking uses Presidio to redact PERSON, EMAIL, CREDIT_CARD

**Retrieval Rails (for RAG)** : Screen chunks before they reach the prompt; risks: sensitive chunks, poisoned context, ungrounded answers; activate with `rails.retrieval.flows: [check retrieval sensitive data]`

**Configuration Example (RAG Chatbot Baseline)** :
```yaml
rails:
  input:
    flows: [self check input, jailbreak detection heuristics]
  retrieval:
    flows: [check retrieval sensitive data]
  output:
    flows: [self check output, self check facts, mask sensitive data on output]
```

**Three Ways to Run:**
- **Library**: import LLMRails in Python – simplest, tightly coupled
- **Server**: run guardrails server, call over HTTP – language-agnostic
- **Sidecar**: dedicated microservice – clean separation, scales on its own

**Rails Aren't Free**: Every LLM-based rail = another model call (4× rails ≈ 4× round-trips); use small/cheap models for rails (gpt-4o-mini); run independent rails in parallel; short-circuit with cheap regex/heuristics first

**Common Pitfalls**: Over-blocking (aggressive rails frustrate users); weak prompts = weak rails; not a silver bullet; latency creep

### 8.7 Spec-Driven Development with GitHub Spec Kit

**The Problem with Vague Prompts**: "Build me a travel planner" – agent invents stack, data model, scope; problem isn't agent – it's that nobody wrote down what "right" meant

**The Mental Shift**: Code-first = intent lives in head, code is only truth, docs rot; Spec-first = intent written down, spec is truth, code follows spec

**What is Spec Kit?**: GitHub open-source toolkit; adds structured slash commands to Claude, Copilot, Gemini (30+ agents); ships full Spec → Plan → Tasks → Implement loop with templates

**The Seven Commands:**
1. `/speckit.constitution` – write non-negotiable principles the agent must follow
2. `/speckit.specify` – describe WHAT and WHY (not how) – user stories + acceptance criteria
3. `/speckit.clarify` – quality gate – asks up to 5 questions about underspecified areas
4. `/speckit.plan` – decide HOW – tech stack, architecture, data model
5. `/speckit.tasks` – break plan into small, ordered, testable tasks
6. `/speckit.analyze` – second gate – checks whole artifact set hangs together
7. `/speckit.implement` – agent writes code against spec and plan

**The Workflow**: constitution → specify → clarify → plan → tasks → analyze → implement

**Enforce in CI: No Spec, No Merge** – GitHub Action that fails PR without spec.md

**When Spec Kit Earns Its Keep**: real features with stakes and edge cases; work an agent will implement; anything multiple people must agree on; projects that outlive one coding session

**Skip It When**: 10-line throwaway script; pure exploration; genuinely don't know goal yet; tiny fixes where spec > change

### 8.8 Structuring Systems: Monoliths, Microservices & Clean Boundaries

**The Trap**: Read how giant companies build software – headline is always "split everything"; copy it – chop small app into many pieces before you need to; result = slower to build, more fragile, harder to change

**The Key Intuition: Rooms vs Letters**: Same program = talking in same room (instant, reliable); another service = mailing a letter (slower, needs address, can get lost)

**Three Shapes:**
- **Monolith**: one program does everything
- **Microservices**: many small separate programs, talk over network
- **Modular Monolith**: one program, clean inner walls, still one app

**The Honest Tradeoff**: Modular monolith = underrated middle ground – most benefit of clean separation, little operational pain

**When to Actually Split:**
1. Needs far more horsepower (resource-hungry piece)
2. Needs its own release schedule (different rhythm)
3. Must be isolated for safety (sensitive)
4. Written in different language

**Three Real Cases:**
1. **Shopify/Instagram**: started as monolith, shipped fast – correct early choice
2. **Amazon/Netflix**: forced to split by scale and team size
3. **Segment**: split too early, operational overhead overwhelmed, merged back – famous walk-back

**The Lesson**: There is no universally correct architecture. There's the right one for your constraints, right now.

**Keeping the Inside Clean (Clean Architecture)** : Core logic (business rules) should not care which tool; outside tools point IN to core; core never points out at specific brand

**The Plug-Shape Idea (Interface)** :
```python
from typing import Protocol

class PaymentGateway(Protocol):
    def charge(self, amount_cents: int, token: str) -> str: ...

class StripeGateway:
    def charge(self, amount_cents, token):
        return "ch_live_123"

class FakeGateway:
    def charge(self, amount_cents, token):
        return "fake_ch_123"

class Checkout:
    def __init__(self, payments: PaymentGateway):
        self.payments = payments
```

**Why Interfaces Are Worth It**: The fake is the whole point – test without real thing, real cost, real network; switching providers later = write one new "device" – not edit whole app

**The Rule That Stops Over-Building**: If there's only ever one version, and a test fake wouldn't help – don't add a plug shape. Just use the thing directly.

---

## GITHUB REPOSITORIES

| Repo | Purpose |
|------|---------|
| `github.com/hasankanaan26/Unit-Testing-Python` | Beginner-friendly unit testing, VS Code Test Explorer |
| `github.com/hasankanaan26/evals-python` | Eval-driven development implementation |
| `github.com/hasankanaan26/advanced-rag-architectures` | Advanced RAG techniques (w7s1-advanced-rag-tagalong) |
| `github.com/hasankanaan26/Advanced-Agentic-AI` | Full agent implementation from Week 4-5 |

---

## SUMMARY STATISTICS

| Category | Topics |
|----------|--------|
| Weeks 1-5 (ML, MLOps, RAG, Agentic AI) | ~366 |
| Week 6 (Deep Learning, CV, Eval-Driven Dev) | ~85 |
| Week 7 (NLP, Transformers, Advanced RAG, GraphRAG, RAGAS) | ~85 |
| Week 8 (Multimodal, Retraining, LoRA/GGUF/Ollama, Career, Transactions, Guardrails, Spec Kit, Architecture) | ~80 |
| **GRAND TOTAL** | **~616 topics** |

---


- Classical ML (regression, classification, feature engineering, selection)
- Deep Learning (NNs, CNNs, transfer learning, PyTorch)
- NLP (text representations, transformers, fine-tuning with LoRA)
- RAG (naive → parent-doc → multi-vector → HyDE → graph → re-ranking)
- RAG Evaluation with RAGAS (context precision/recall, faithfulness, response relevancy)
- Agentic AI (tool calling, ReAct, LangGraph, HITL, multi-agent)
- MLOps (model registry, validation, observability, drift, shadow scoring, champion/challenger)
- Production patterns (queues, idempotency, outbox, guardrails with NeMo)
- Infrastructure (Docker, AWS, FastAPI, Ollama, GGUF)
- Prompt Engineering (all techniques from zero-shot to ReAct)
- Software engineering (spec-driven dev with Spec Kit, clean architecture, transactions)
- Eval-driven development (tests vs evals, dataset curation, LLM-as-judge calibration)


Understood. Here is the cleaned version without the project-related statement.

---

# AI ENGINEERING BOOTCAMP – COMPLETE TOPIC REFERENCE FOR CLAUDE

*Use this document to understand everything the user has learned. Every topic from all 62 files across Weeks 1-8 is captured below with technical details.*

---

## HOW TO USE THIS DOCUMENT

I have completed an 8-week AI Engineering Bootcamp covering:
- Classical ML (regression, classification, feature engineering)
- Deep Learning (neural networks, CNNs, transfer learning)
- NLP (text representations, transformers, fine-tuning)
- Computer Vision (image classification, detection, segmentation)
- RAG (naive to advanced: parent-doc, multi-vector, HyDE, graph, re-ranking)
- Agentic AI (tool calling, ReAct, LangGraph, multi-agent)
- MLOps (model registry, validation, observability, drift detection)
- Production patterns (queues, idempotency, outbox, guardrails)
- Eval-driven development (tests vs evals, RAGAS, LLM-as-judge)
- Infrastructure (Docker, AWS, FastAPI, Ollama, GGUF)
- Prompt Engineering (all techniques from zero-shot to ReAct)
- Software engineering (spec-driven dev, clean architecture, transactions)

---

## WEEK 1: MACHINE LEARNING FOUNDATIONS & EDA

### 1.1 Artificial Intelligence Fundamentals
- **Definition**: AI creates systems that perform tasks requiring human intelligence (learning, reasoning, problem-solving)
- **Key branches**: Machine Learning (learns from data), NLP (human language), Computer Vision (visual information), Generative AI (creates new content)
- **ML limitations**: cannot predict with certainty (only probabilities), cannot work without data, correlation ≠ causation, cannot replace domain expertise, cannot make ethical decisions independently

### 1.2 Supervised Learning
- **Definition**: Predict a specific value from labeled training data
- **Classification**: Predict categories (weather type, will customer buy, will patient be readmitted)
- **Regression**: Predict exact values (temperature, customer spend, patient stay length)
- **Labels**: Every training example needs correct answer; labeling is expensive, slow, and sometimes inconsistent
- **Good dataset criteria**: Size (more examples), Quality (garbage in, garbage out), Representativeness (reflects real world), Balance (all categories represented)

### 1.3 Traditional Programming vs Machine Learning
- **Traditional**: Human writes explicit rules (IF humidity > 80% AND wind > 20 km/h THEN Rainy) – breaks when rules don't match reality
- **ML**: Data reveals rules; model discovers patterns from thousands of examples; generalizes to new, unseen situations

### 1.4 How a Model Learns (The Learning Loop)
1. Make prediction using current internal parameters
2. Compare prediction to true answer
3. Measure the error (how wrong was it?)
4. Adjust internal parameters to reduce error
5. Repeat thousands of times until error is minimized
- **The model asks**: "How wrong am I, and in which direction?"

### 1.5 Underfitting vs Overfitting
- **Underfitting**: Model too simple, high bias, fails to capture patterns
- **Overfitting**: Model too complex, high variance, memorized training data
- **Goal**: Both scores close and both acceptable

### 1.6 The ML Lifecycle
Complete pipeline from problem framing → data collection → EDA → preprocessing → model training → evaluation → deployment → monitoring

### 1.7 Data Foundations
- **Data sources**: Questionnaires, surveys, interviews, social media activity, transactions, sensors/IoT, web scraping, government records
- **Storage**: Local files, cloud storage, public URLs, built-in datasets
- **Formats**: CSV (simple, portable), Excel (manual editing, multi-sheet), JSON (nested structures, API payloads)

### 1.8 Exploratory Data Analysis (EDA)
- **Why it matters**: Understand structure, detect issues early, generate hypotheses, reduce modeling mistakes
- **Checklist**:
  - Shape and schema: rows, columns, data types
  - Missing values: NaN or placeholders (?, -)
  - Summary statistics: mean, mode, min/max, quartiles
  - Distributions: how data is spread
  - Outliers and anomalies: unusual data points
- **Descriptive statistics**: Extreme ranges impact model stability; skewed targets affect error interpretation; unusual quartiles hint at caps or collection limits

### 1.9 pandas DataFrame
- Rows = observations, Columns = features, Index = row label
- `df.shape` → (rows, columns)
- `df.dtypes` → data type of each column
- `df.head()` → first 5 rows
- `df.info()` → shape + types + non-null counts

### 1.10 ML Starter's Toolkit
- **Python**: primary language
- **pandas**: tabular data manipulation
- **NumPy**: arrays and mathematical operations
- **scikit-learn**: ML models
- **Google Colab**: cloud-based notebooks for experimentation
- **Notebooks vs Scripts**: Notebook = exploratory, iterative, visual; Script = repeatable, versionable, production-friendly

---

## WEEK 2: PREPROCESSING, ENCODING, SCALING, & TOOLING

### 2.1 Missing Values Handling
- **What are missing values**: NaN (not recorded, not applicable, unknown) or placeholders (?, -)
- **Strategies**:
  1. Drop column (if >50% missing or low signal)
  2. Drop row (if very few rows affected and column critical)
  3. Fill with mean or median (numeric, no strong meaning)
  4. Fill with mode (categorical, no strong meaning)
  5. Fill with constant ("None", 0, "Unknown")
  6. Forward/backward fill (time series only)
- **Rules of thumb**: >50% missing → consider dropping; null by design → fill with "None" or 0; genuinely missing → median/mode; **always impute using train statistics only**

### 2.2 Categorical Encoding
- **Why models need numbers**: Most algorithms use matrix operations; "Neighborhood = OldTown" is meaningless to math formula
- **Label Encoding**: Each category gets a number (0, 1, 2...) – preserves ordinal relationships
- **One-Hot Encoding**: Each category becomes a binary column – creates new columns
- **Ordinal vs Nominal**:
  - Ordinal: meaningful order (quality ratings, size buckets) – order of encoding matters
  - Nominal: no meaningful order (color, neighborhood) – order doesn't matter
  - Wrong choice causes models to learn incorrect relationships
- **Cardinality Problem**: High cardinality (many unique values) creates too many columns; solutions include grouping rare categories, dropping, or target encoding

### 2.3 Feature Scaling
- **Why scaling matters**: Algorithms using distances or gradients treat large-scale features as more important
- **Example**: LotArea (1,300–215,000) vs OverallQual (1–10) – LotArea dominates without scaling
- **Three Scalers**:
  - **StandardScaler**: subtract mean, divide by std → result: mean=0, std=1 (sensitive to outliers)
  - **MinMaxScaler**: compress to [0,1] range (very sensitive to outliers)
  - **RobustScaler**: uses median and IQR (robust to outliers, use when outliers present)

### 2.4 Feature Pipelines (sklearn.pipeline)
- **Problem with manual preprocessing**: Hard to reproduce, easy to apply in wrong order, hard to share, execution order not guaranteed
- **Pipeline**: Chain of (name, transform) steps; each step's output feeds the next; last step can be a model
- **Guarantees**: Correct order, fit-on-train-only, single save
- **ColumnTransformer**: Apply different transformations to different column groups (numeric vs categorical)

### 2.5 Data Splitting & Validation
- **Train/Test Split**: 70-90% train, 30-10% test
- **Train/Validation/Test Split (Three-Way)**: 60/20/20 – train learns, validation tunes (used many times), test evaluates once at end
- **Methods**: `train_test_split` (simple, set random_state for reproducibility), `StratifiedShuffleSplit` (for imbalanced classification)
- **Features (X) vs Target (y)**: No leakage between X and y
- **Validation Set as Decision Budget**: Every model comparison uses validation set; test set used once at very end

### 2.6 Regression Models
- **Linear Regression**: Baseline, fits best straight line, fast, interpretable, assumes linearity
- **Decision Trees**: Tree-structured, splits on one feature at a time; deep trees = overfit (high variance), shallow trees = underfit (high bias)
- **Random Forest**: Ensemble of trees, handles non-linearity, robust to outliers
- **Gradient Boosting**: Trains sequentially, learns from previous errors, often best accuracy

### 2.7 Regression Metrics
- **MAE (Mean Absolute Error)**: Same unit as target, stable, easy to explain
- **MSE (Mean Squared Error)**: Punishes large misses heavily, units are squared
- **RMSE (Root Mean Squared Error)**: Target units, sensitive to outliers
- **R-squared**: Variance explained vs predicting mean (can be negative on new data)
- **Best practice**: Always report 2+ metrics

### 2.8 Model Workflow & Deployment
- `fit(X_train, y_train)` → `predict(X_test)` → compare predictions with truth
- `joblib.dump(model, path)` and `joblib.load(path)` for saving/loading models
- **Why save**: Reproducibility and deployment

### 2.9 Prompt Engineering (Complete)
- **Definition**: The art and science of communicating intent to AI models
- **Three principles**: Clarity > Cleverness, Context is Everything, Iterate Don't Guess

**Techniques:**
- **Zero-Shot**: Ask directly with no examples – be specific about task, format, constraints
- **Few-Shot**: Provide input/output examples so model learns pattern – cover ALL categories, include edge cases
- **Chain-of-Thought (CoT)**: "Think step by step" – improves math, logic, analysis; can be simple or structured with defined reasoning steps
- **Role/Persona**: Tell model who to be – shapes tone, vocabulary, depth, perspective
- **System vs User**: System = persistent rules (employee handbook), User = per-turn request (customer walking in)
- **Structured Output**: Specify exact format (JSON, XML, tables, CSV) – show the schema
- **Prompt Chaining**: Break complex tasks into sequence; output of one feeds the next
- **Temperature**: Low (0-0.3) = focused, deterministic; High (0.7-1.0) = creative, varied
- **Delimiters**: Use markers (triple quotes, XML tags, dashes) to separate instructions from data
- **Negative Prompting**: Tell model what to AVOID; combine positive + negative for best results

**Prompt Injection & Defense:**
- **What it is**: Untrusted input hijacks model behavior (analogous to SQL injection for LLMs)
- **Three defense layers**:
  1. Delimiters: wrap untrusted content in boundaries + explicit instruction to ignore embedded commands
  2. System/User Split: keep instructions in system prompt (higher priority)
  3. Output Validation: check response format before showing to user
- **Rule of thumb**: Never trust user input – always assume adversarial

**ReAct-Style Agents:**
- Pattern: Reasoning → Action → Observation → Reasoning (loop)
- Format: Thought → Action: search("[query]") → Observation → Final Answer
- Critical: "Never fabricate Observation" – prevents hallucination

### 2.10 LLMs & Hosted Models
- **How LLMs work**: Trained on massive text → learns patterns → you give prompt → predicts next words
- **Key insight**: LLMs don't "understand" – they predict; they can hallucinate (confident but wrong)
- **Terminology**: Token (~¾ word), Context Window (max tokens), Temperature (randomness), Hallucination, Fine-tuning
- **Transformer Architecture (2017)**: Self-attention (words matter to each other), parallel processing (reads all at once), massive scale (billions of parameters)
- **Hosted vs Local**: Hosted = API access, state-of-the-art, costs money, data leaves machine; Local = download, free, private, offline, needs GPU
- **Major providers**: OpenAI (GPT-4o), Anthropic (Claude), Google (Gemini), Open-source hosted (Llama, Mistral, DeepSeek)

### 2.11 AWS Services
- **S3 (Simple Storage Service)**: Stores files, any size, event-driven
- **Lambda**: Runs code without servers, event-driven, stateless
- **Bedrock**: Foundation models via API (Claude, Llama, Mistral) – pay per token
- **Polly**: Text-to-speech, natural voices, MP3/OGG output
- **SES (Simple Email Service)**: Send emails programmatically, attachments, HTML
- **Use case**: Research paper PDF uploaded to S3 → Lambda triggers → Bedrock summarizes + Polly narrates → SES sends email digest

### 2.12 Docker
- **What it is**: Packages application + dependencies into container – "Package once, run anywhere"
- **Key concepts**: Image (read-only blueprint, like class), Container (running instance, like object), Dockerfile (recipe)
- **Commands**: `docker pull`, `docker build -t`, `docker run -p`, `docker ps`, `docker stop`, `docker images`
- **Dockerfile**: FROM (base image), WORKDIR (working directory), COPY, RUN, EXPOSE, CMD
- **Docker Compose**: Define multi-container apps with YAML; `docker compose up` starts everything

---

## WEEK 3: FEATURE ENGINEERING, SELECTION & VISUALIZATION

### 3.1 Feature Engineering
- **Definition**: Transforming raw facts into better predictive signals – not adding new data, reshaping what you have
- **"Better data beats better algorithms"** – Kaggle winners spend 70-80% of time on feature engineering
- **Four types**:
  1. **Domain features**: Combine columns using real-world knowledge (TotalSF = 1stFlrSF + 2ndFlrSF + TotalBsmtSF)
  2. **Temporal features**: Compute elapsed time (HouseAge = YrSold - YearBuilt)
  3. **Interaction features**: Multiply columns for joint effects (QualArea = OverallQual × GrLivArea)
  4. **Mathematical transforms**: Change distribution (log1p on LotArea for right-skewed data)
- **Binary indicators**: Convert sparse numeric columns to presence/absence (HasPool, HasFireplace, HasGarage)
- **Leakage boundary**: Safe = features known at inference time; Unsafe = using target variable or full dataset before splitting
- **Three rules**: Always validate with val RMSE, never leak, stop when last 3 features gave <1% improvement

### 3.2 Feature Selection
- **Why it matters**: Noise features add variance without bias reduction; correlated features split model weight (multicollinearity); computational cost; overfitting risk
- **The Curse of Dimensionality**: In 100D, 100 points are isolated → nearest neighbors not nearby; distance/density concepts break down
- **Selection methods**:
  - **Variance Threshold**: removes near-zero variance features (fast, no model)
  - **Correlation Filter**: drop one from any pair with |r| > 0.90 (fast, no model)
  - **RFE (Recursive Feature Elimination)**: trains model repeatedly, removes weakest (slow, uses model)
  - **Tree Importance**: feature importance from trained tree model (fast, one fit, uses model)
- **Risk of over-selecting**: Too few features = underfit; always validate with val RMSE before and after

### 3.3 Visualizing Representations (PCA & t-SNE)
- **The high-dimensional space problem**: Ames has ~200 dimensions; humans perceive up to 3 dimensions
- **PCA (Principal Component Analysis)**:
  - Finds axes of maximum variance (linear combination of original features)
  - PC1 captures most variance, PC2 orthogonal next most
  - Requires StandardScaler before PCA
  - Linear only, components not interpretable as single concepts
  - Variance explained: 1 component = ~35%, 2 = ~50%, 5 = ~65%, 20 = ~82%, 50 = ~91%
- **t-SNE (t-distributed Stochastic Neighbor Embedding)**:
  - Preserves local neighborhood structure (which points are nearest neighbors)
  - Finds dense subgroups (quality tiers, neighborhood clusters)
  - Slower, non-deterministic, not for modeling
- **PCA vs t-SNE**: PCA fast and deterministic (seconds), preserves global structure, use for modeling; t-SNE slow and non-deterministic (minutes), preserves local clusters, not for modeling

### 3.4 Comparing Representations
- **Experimental design**: Raw (249 features) vs +Engineered (~260) vs +Selected (~160) vs PCA-50 (50 components)
- **Evaluation protocol**: Fit on X_train → evaluate on X_val → record val RMSE and R² → record train RMSE (monitor gap) → select best on val RMSE → evaluate winner on X_test once
- **Key lessons**:
  - Engineered > Raw: domain features added signal model couldn't recover
  - Selected ≈ Engineered: selection removed noise but tree model already robust
  - PCA < Raw: compression loses signal for tree models
  - The right representation depends on the model family

---

## WEEK 4: CLASSIFICATION, RAG & AGENTIC AI

### 4.1 Classification Essentials
- **From regression to classification**: Continuous number → category/label; MSE/RMSE → Log loss/cross-entropy; single number → probability per class
- **Classification metrics**:
  - **Confusion Matrix**: TP (correctly predicted churn), TN (correctly predicted no churn), FP (wasted intervention), FN (missed opportunity)
  - **Precision** = TP/(TP+FP): "Of all predicted churners, how many actually churned?"
  - **Recall** = TP/(TP+FN): "Of all actual churners, how many did we catch?"
  - **F1** = 2 × (Precision × Recall)/(Precision + Recall): harmonic mean
  - **Accuracy** = (TP+TN)/Total: misleading with imbalanced classes
  - **ROC/AUC**: probability model ranks positive above negative; 0.5 = random, 1.0 = perfect
- **Class imbalance**: Telco has 73.5% No Churn / 26.5% Churn; strategies: `class_weight='balanced'`, threshold adjustment, SMOTE
- **Calibration**: Well-calibrated = predicted probability ≈ actual proportion; transformers tend to be overconfident
- **Threshold analysis**: Default 0.5; lower (0.3) = higher recall, more false alarms; higher (0.7) = higher precision, miss more churners

### 4.2 Hyperparameter Tuning
- **Parameters vs Hyperparameters**: Parameters learned from data during training; hyperparameters chosen before training
- **GridSearchCV**: Exhaustive, tries every combination – best for small search spaces (<20 configs)
- **RandomizedSearchCV**: Tries random configurations – better for large spaces
- **StratifiedKFold**: Ensures each fold maintains same class ratio – prevents validation set leakage
- **Key GradientBoosting hyperparameters**: n_estimators (100-500), learning_rate (0.01-0.2), max_depth (2-6), min_samples_leaf (1-20), subsample (0.7-1.0)
- **Scoring metrics for tuning**: roc_auc (ranking), f1 (default for imbalanced), recall (maximize catching), precision (minimize false alarms)

### 4.3 Experiment Tracking & Reproducibility (MLflow)
- **What to log**: Model class and ALL hyperparameters, train/val/test split config, preprocessing config, evaluation metrics, date/time, library versions, dataset hash
- **MLflow**: Open-source platform; Experiment = named collection of runs; Run = single execution with params, metrics, artifacts
- **Reproducibility checklist**:
  1. `random_state=42` on all random operations
  2. `numpy.random.seed(42)` at top of notebook
  3. Log library versions
  4. Log dataset filename, row count, column count, md5 hash
  5. Log all hyperparameters
  6. Save model with `joblib.dump`
  7. Notebook runs cleanly from top to bottom

### 4.4 RAG (Retrieval-Augmented Generation) – Foundation

**The Problem:**
- LLMs hallucinate when they don't know the answer
- Context windows are limited
- Every token costs money
- More text = worse answers

**The Solution (Grounding):**
- Paste real context into prompt before asking question
- But can't paste everything → need retrieval

**The RAG Loop (3 Steps):**
1. **Retrieve**: find relevant chunks from knowledge base
2. **Augment**: build prompt with context + question
3. **Generate**: LLM answers based ONLY on retrieved context

**Loading & Chunking:**
- Loading: convert many formats to plain text
- **Chunking strategies**:
  - Fixed-size with overlap: simple, works on any text, may cut mid-sentence
  - Section-based: chunks match meaning, needs structured documents
- **Chunk size tradeoff**: too small = missing context, too large = irrelevant info

**Embeddings & Vector Stores:**
- **Embedding**: coordinate for meaning – fixed-length vector where similar ideas are near each other; distance = similarity; learned from billions of sentences
- **Why semantic search beats keyword**: "annual leave policy" vs "Employees get 20 vacation days" – no keyword match, but semantic match works
- **Vector Store (ChromaDB)**: Stores embeddings + metadata; `POST /ingest` (chunks → embeddings → store), `POST /search` (query → top-k chunks with distances)
- **Metadata**: source file, chunk ID, filters for debugging

**The RAG Prompt:**
- **Strict (Grounded)** : "Answer only from the context below. If the answer isn't there, say 'I don't know.' Cite your sources."
- **Loose**: "Here's some context and a question – answer it."

**Source Attribution:**
- Always return sources – enables trust, debugging, compliance

**RAG vs Plain LLM:**
- "How many vacation days?" → Plain: "15 days" (made up); RAG: "20 days" with source
- "Capital of France?" → Plain: "Paris" (from training); RAG: "I don't know" (not in docs)

**RAG Failure Modes:**
- **Confidence scoring (4 levels)** : High (0.8-1.0): strong match; Medium (0.6-0.8): reasonable; Low (0.4-0.6): weak, verify; None (<0.4): no relevant content
- **Refusing to answer is a feature**: When top scores below threshold → stop before LLM invents something – faster, cheaper, more honest
- **Questions RAG struggles with**: subjective, temporal, cross-domain synthesis, world knowledge (already in LLM)
- **Transparency**: UI shows confidence badge, sources, debug info; embedding visualization shows clusters

### 4.5 Agentic AI – Complete

**What is an Agent?**
- An LLM that can decide which actions to take
- LLM alone: generates text only
- LLM + Tools = Agent: generates text AND takes action

**Session 1: Tool Calling**
- **How it works**:
  1. Code sends prompt + tool schemas (JSON Schema)
  2. LLM returns a tool call (structured request, never executes)
  3. Your code executes the tool
  4. Result returned to LLM
- **Tool Schema fields**: name (identifier), description (MOST important – LLM reads to decide), parameters (JSON Schema), required (args that must be provided)
- **Tool Registry pattern**: single dict mapping tool name → schema + executor; single source of truth, easy to extend, easy to gate
- **Security**: validate everything, treat LLM output as untrusted input

**Session 2: Agent Loop (ReAct)**
- **The ReAct pattern**: Reasoning → Action → Observation → Reasoning (loop)
- **Agent loop code (~20 lines)** :
```python
for step in range(max_steps):
    response = call_llm_with_tools(messages, tools)
    if response["finish_reason"] == "stop":
        return answer
    for tool_call in response["tool_calls"]:
        result = execute_tool(tool_call)
        messages.append(tool_result_message(tool_call, result))
```
- **Critical components**: messages = agent's memory; max_steps = safety cap (default 10); finish_reason = "stop" when LLM done
- **Why agents loop forever**: tool result not appended, LLM never decides it has enough, tool returns empty/error, two tools that re-trigger each other
- **Read vs Write tools**: Read = safe (calculator, search, clock) always allowed; Write = dangerous (task creation, file write) need gates

**Session 3: Safety & Control (LangGraph)**
- **LangGraph vs Manual**: 5 lines vs 50 lines; automatic state management; built-in checkpointing (persistence across restarts); streaming; HITL
- **LangGraph ReAct Agent**:
```python
agent = create_react_agent(model, tools, checkpointer=MemorySaver())
result = agent.invoke({"messages": [("user", goal)]},
                      config={"configurable": {"thread_id": "1"}})
```
- **Why thread_id matters**: same ID = same conversation (memory across restarts)
- **Injection Detection (regex patterns)** : "ignore all previous instructions", "you are now a...", "forget all your rules", "pretend you are unrestricted", "system:"
- **Defense in Depth (4 layers)** :
  1. Input sanitization (cheapest, catches noise)
  2. Injection detection (regex/ML on prompt)
  3. Tool permissions (whitelist per request)
  4. Human-in-the-loop (manual approval for writes)
- **Human-in-the-Loop (HITL)** : pause before write operations, human approves/denies; required for deletions, payments, emails

**Session 4: Orchestration & Observability**
- **Multi-Agent Systems**: Complex goals overwhelm single agent; specialized agents collaborate better
- **Planner-Executor Pattern**: Planner breaks goal into steps (1-5), no tool access, uses Pydantic structured output; Executor runs each step with tools; Safety layer checks everything
- **Tracing (Observability)** : Structured log of every step with timing; total duration, step durations, tool outputs, status; "You can't debug what you can't see"

---

## WEEK 5: MLOPS & PRODUCTION PATTERNS

### 5.1 Model Artifacts & Versioning
- **Model artifact**: folder containing model pickle + preprocessing pipeline + metadata – "All three or none"
- **Model registry**: Run → Registered Model → Version → Stage (Staging, Production, Archived)
- **MLflow registry mechanics**:
```python
mlflow.sklearn.log_model(pipeline, artifact_path="model",
                         signature=signature, registered_model_name="model")
client.transition_model_version_stage(name, version, stage="Staging")
loaded = mlflow.sklearn.load_model("models:/model/Staging")
```
- **Semantic versioning for ML**: v0.1.0 (initial), v0.1.1 (patch, ≤0.5% metric delta), v0.2.0 (minor, new hyperparameters/features), v1.0.0 (major, input schema changed)
- **One staging version rule**: assert only ONE model version in Staging – "If two models are in Staging, you have a bug, not a backup"

### 5.2 Input Validation & Robust Inference
- **Why validation matters**: The world sends garbage – missing fields, wrong types, unknown categorical values; all three pass silently if you let them
- **Pydantic v2**:
```python
class TelcoChurnRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    Contract: Literal['Month-to-month', 'One year', 'Two year']
    tenure: int = Field(ge=0, le=100)
```
- **Closed enums via Literal**: If not in list, not a request – validation fails loudly
- **Layered defense**: Outer = Pydantic rejects loudly with validation_error; Inner = OneHotEncoder(handle_unknown='ignore') silently zero-encodes
- **Threshold tuning as cost decision**: Telco churn = cost(FN) >> cost(FP) → bias recall; fraud detection = cost(FP) >> cost(FN) → bias precision

### 5.3 Observability – Local vs Production
- **The iceberg problem**: Local works, production breaks
- **Structured logs vs print**: print is unstructured and unqueryable; structured logs have request_id, model_version, latency_ms, prob, threshold, warning
- **The Four Golden Signals**:
  - **Latency**: how fast (p50, p95, p99)
  - **Errors**: how often it breaks (validation_error/min, model_error/min)
  - **Traffic**: how much it serves (requests/min)
  - **Saturation**: how full the box is (CPU%, memory%, queue depth)
- **PSI (Population Stability Index)** for numerics: PSI = Σ(p_cur - p_ref)·ln(p_cur/p_ref); thresholds: <0.10 OK, <0.20 WATCH, <0.25 ALERT, ≥0.25 ALARM
- **Chi-square for categoricals**: scipy.stats.chisquare(observed, expected); p < 0.01 triggers ALERT
- **Drift ≠ Accuracy Loss**: Drift detection asks "has the world shifted?"; Accuracy asks "is model still right?"; both can fire independently
- **Alert rules in code**: check PSI values ≥0.20, label drift ≥5pp, p99 latency >200ms → return reasons list

### 5.4 End-to-End Production Pipeline
- **The production pipeline flow**: JSON request → Pydantic validate → predict_proba → log + drift buffer → JSON response
- **Two response shapes**:
  - **Success**: ok=True, request_id, model_version, threshold, churn_probability, churn_label, latency_ms, warning
  - **Error**: ok=False, request_id, error, details, latency_ms
- **Three failure paths**:
  1. Bad JSON → invalid_json (microseconds)
  2. Bad shape (missing field, wrong type, unknown enum) → validation_error (microseconds)
  3. Model crash (predict_proba raised) → model_error (logs traceback, recovers)
- **The serve() function pattern**: try-catch for each failure type, rolling window for drift detection, warning included in success response

### 5.5 Queues with Redis

**The Problem:**
- Slow tools block the request (30-second scrape holds HTTP connection)
- Bursts kill you (ten users at once → ten parallel scrapes → memory blows up)
- Crashes lose work (app dies mid-scrape → work is gone → user retries)

**The Solution: Decouple Request from Work**
- Return job_id instantly; workers consume jobs at their own pace; users poll for result

**Four Components:**
- **Producer**: submits jobs, knows the what (app/queue/client.py)
- **Broker**: holds queued jobs, hands them out (Redis via arq)
- **Consumer/Worker**: pulls jobs, runs them, reports results (app/workers/runner.py)
- **Result store**: finished work so producer can read it (app/queue/results.py)

**Delivery Guarantees:**
- **At-most-once**: ≤1 delivery – losing job preferable to running twice
- **At-least-once**: ≥1 delivery – default; pair with idempotency
- **Exactly-once**: the myth – can't be guaranteed across distributed systems
- **Production answer**: at-least-once + idempotent tasks = exactly-once effects

**Idempotency:**
- **Definition**: Running twice with same input produces same effect as running once
- **Examples**: SET user.email = "x" (idempotent), INCREMENT view_count (not idempotent), UPSERT (idempotent), INSERT INTO charges (not idempotent)
- **CP4 two-layer defense**:
  1. Producer-side: check if result already exists
  2. Broker-side: arq refuses second job with same job_id while first is queued/running

**Retries: Transient vs Permanent:**
- **Transient** (5xx, 429, network timeout, connection reset): retry with exponential backoff + jitter (1s, 2s, 4s, 8s)
- **Permanent** (4xx, validation error, schema mismatch): fail fast → send to DLQ

**Dead Letter Queue (DLQ):**
- **Wrong answer**: silently drop job (missing job, no idea it was missing)
- **Right answer**: send dead jobs to DLQ – separate Redis list for inspection
- **When job dies permanently**: write tombstone, push to DLQ list, fire webhook, log warning
- **Rule**: never let a job vanish – either it succeeds, or tombstone is visible somewhere

**Job Lifecycle (5 states)**: QUEUED → RUNNING → COMPLETED; on exception → transient? retry → permanent? DEAD_LETTER

**Worker Scaling**: `docker compose up -d --scale worker=4` – same code, multiple processes

**Lease/Visibility Timeout**: Broker gives worker a lease (default 30s); miss deadline → broker assumes worker crashed and redelivers

### 5.6 MCP (Model Context Protocol)
- **The problem MCP solves**: Without MCP, each tool requires glue code (schema + function + wiring) from scratch
- **MCP = USB-C for AI agents**: one standard plug so any agent can use any tool
- **API vs MCP**: API = one specific door (each has own URL, params, auth, response format); MCP = universal plug (every server speaks same protocol)
- **What an MCP server does**:
  - Discovery: Agent asks "what can you do?"; Server replies with available tools
  - Execution: Agent calls tool with inputs; Server returns results
- **MCP does NOT replace APIs** – MCP wraps them; your agent only learns ONE shape (MCP)
- **When to use**: building AI agent = default choice; reusable tools across agents = built for this

### 5.7 MCP vs A2A (Agent-to-Agent)
- **MCP**: connects agent to tools and data; vertical relationship (agent → tool); other side is dumb (just executes); answers "How do I give my agent capabilities?"
- **A2A**: connects agent to other agents; horizontal relationship (agent ↔ agent); other side is smart (reasons and plans); answers "How do I let my agent collaborate?"
- **A2A core ideas**: Agent Cards (manifest describing skills), peer-to-peer (discover and call over HTTP), task lifecycles (streaming, multi-turn, auth)
- **They work together**: Supervisor uses A2A to talk to Researcher; Researcher uses MCP to talk to Web search + Vector DB

### 5.8 Agents as Production Software (Week 5 – 4 Sessions)

**The mental model**: Agents are software systems. Architect them. Persist them. Test them. Operate them.

**The four upgrades:**
1. **Multi-Agent Architectures**: choose topology, handoffs, LangGraph Studio
2. **Memory & Persistence**: checkpoints, resumable workflows, survive restarts
3. **Agent Software Engineering**: tests, reproducibility, prompt versioning
4. **Long-Running Tools**: queues, workers, idempotency, retries, DLQ

**When to split (multi-agent):**
- Distinct skills, different tool sets per role, different prompts that conflict, want one agent to critique another
- **Don't split when**: one agent + better prompt would do, sub-tasks share context, latency budget tight, splitting just to look sophisticated

**Three topologies:**
- **Supervisor**: central agent decides which specialist to call – easy to debug
- **Hierarchical**: teams of teams – top-level supervisor delegates to sub-supervisors
- **Swarm/Handoff**: peer agents transfer control based on context – flexible, harder to control

**LangGraph primitives (3)** :
- **STATE**: typed dict that flows through graph – every node reads and updates
- **NODES**: async functions that take state and return Command (what to update, where to go next)
- **EDGES**: routes between nodes; conditional edges let graph branch on state

**Memory & Persistence:**
- **Short-term**: within single run, stored in graph state via Redis checkpointer
- **Long-term**: across sessions/users, stored in Postgres
- **Checkpointing**: save state at every node; resume anywhere; time-travel when something breaks
- **thread_id is everything**: same thread_id = same conversation (memory across restarts)

**Agent Software Engineering (4 practices)** :
1. **Test**: unit + integration, deterministic mocks, snapshot tests for trajectories
2. **Debug**: trace → replay → fix – reproduce failure, fix with confidence
3. **Version**: prompts and models in source control – pinned, reviewed, rolled back
4. **Reproduce**: seeds, deterministic mocks, snapshots – every run reproducible

**Mocking the LLM (non-negotiable)** : Replace chat model with fake at fixture level; return canned responses; tests run in milliseconds, $0, 100% reproducible

**Snapshots**: capture sequence of nodes visited; compare to 'golden' trajectory; fail if agent took weird path

**Tests vs Evals**: Tests = deterministic, fast, every commit, check structure; Evals = probabilistic, slow, nightly, measure quality

---

## WEEK 6: DEEP LEARNING & COMPUTER VISION

### 6.1 Deep Learning Fundamentals

**Why Deep Learning is "Worth Leaving" sklearn:**
- sklearn LogisticRegression: linear decision boundary, ~30 features
- Deep MLP/NN: non-linear, can fit images, scales to millions of features

**A Digital Neuron**: Inputs → weights → sum → activation → output

**Multi-Layer Perceptron (MLP)** : Input layer → hidden layer(s) → output layer

**Activation Functions:**
- **ReLU**: max(0,x) – most common for hidden layers
- **Sigmoid**: 1/(1+e^-x) – for binary classification output
- **Softmax**: for multi-class classification output
- **Tanh**: range [-1,1]

**Forward Pass:**
```python
Z1 = X @ W1 + b1           # (N, hidden_dim)
A1 = np.maximum(0, Z1)     # ReLU activation
Z2 = A1 @ W2 + b2           # (N, output_dim)
P = sigmoid(Z2)             # probability
```

**Loss Functions:**
- **Binary Cross-Entropy (BCE)** : for binary classification
- **Categorical Cross-Entropy (CCE)** : for multi-class classification
- **MSE**: for regression

**Backward Pass (Backpropagation)** : Chain rule applied to compute gradients; gradients flow from output back to input

**Stochastic Gradient Descent (SGD)** : Update rule: `W -= LR * dW`; mini-batch updates (not each sample, not full dataset)

**Training Loop:**
```python
for epoch in range(50):
    perm = np.random.permutation(N_train)
    for start in range(0, N_train, batch_size):
        idx = perm[start:start+batch_size]
        Xb, yb = X_train[idx], y_train[idx]
        _, cache = forward(Xb, W1, b1, W2, b2)
        dW1, db1, dW2, db2 = backward(cache, yb, W2)
        W1 -= LR * dW1; b1 -= LR * db1
        W2 -= LR * dW2; b2 -= LR * db2
```

**Three Sanity Checks:**
1. Loss starts at expected value (e.g., -log(0.5) for balanced binary)
2. Overfit a tiny subset (10 samples) → loss → 0
3. Train/val gap tells overfitting story

### 6.2 PyTorch Fundamentals

**nn.Module (The PyTorch Building Block)** :
```python
class TinyMLP(nn.Module):
    def __init__(self, input_dim=1024, hidden_dim=64, output_dim=1):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, output_dim)
    def forward(self, x):
        z1 = self.fc1(x)
        a1 = F.relu(z1)
        z2 = self.fc2(a1)
        return z2  # raw logits
```

**Byte-Identical Diagnostic**: Verify PyTorch implementation matches NumPy reference; max |Δ| < 1e-6 → correct

**From Binary to Multi-Class:**
- Output dim: 1 → 37
- Activation: Sigmoid → Softmax
- Loss: BCE → CrossEntropyLoss
- Prediction: threshold at 0.5 → argmax
- Random baseline: 0.50 → 0.027 (1/37)

**The PyTorch Training Stack:**
```python
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=30)

for epoch in range(EPOCHS):
    for xb, yb in train_loader:
        optimizer.zero_grad()
        loss = criterion(model(xb), yb)
        loss.backward()
        optimizer.step()
    scheduler.step()
```

**Why Adam Beats Plain SGD**: SGD = same LR for every parameter; Adam = per-parameter adaptive LR using moving averages of grad and grad² – default choice

**Early Stopping**: Track best validation loss; stop if no improvement for N epochs (e.g., 8); restore best weights at end

**Learning Rate Schedulers**: CosineAnnealingLR anneals from initial LR to ~0 over T_max epochs – prevents overshooting

### 6.3 CNNs and Image Pipelines

**Why an MLP Is Wasted on Images**: Pixel (0,0) and (1,0) are neighbors in 2D space; MLP treats them as independent dimensions; 1920×1080 image has 2,073,600 pixels → billions of parameters

**Convolution (The CNN Building Block)** : 3×3 kernel slides over image; 9 weights × 1 bias = 10 parameters (vs 1024 for fully connected); preserves spatial locality

**The PyTorch Image Pipeline:**
```python
train_tf = T.Compose([
    T.Resize(72), T.RandomCrop(64),
    T.RandomHorizontalFlip(p=0.5),
    T.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
    T.ToImage(), T.ToDtype(torch.float32, scale=True),
    T.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])
```

**Data Augmentation (Free Training Data)** : Flipped, color-jittered, cropped, rotated

**TinyCNN Architecture:**
```python
class TinyCNN(nn.Module):
    def __init__(self, n_classes=37):
        self.conv1 = nn.Conv2d(3, 32, 3, padding=1)
        self.conv2 = nn.Conv2d(32, 64, 3, padding=1)
        self.conv3 = nn.Conv2d(64, 128, 3, padding=1)
        self.pool = nn.MaxPool2d(2, 2)
        self.gap = nn.AdaptiveAvgPool2d(1)  # global average pooling
        self.fc = nn.Linear(128, n_classes)
        self.dropout = nn.Dropout(0.3)
```

**Global Average Pooling vs Flatten**: Flatten → large feature vector, many params; GAP → one value per channel → far fewer params

**Week 6 Progression:**
- Day 1: NumPy MLP, cat/dog binary → 0.676
- Day 2: PyTorch MLP, 37-class breed → 0.071
- Day 3: Small CNN + augmentation → 0.155
- Day 4: Pretrained ResNet → ~0.87

### 6.4 Transfer Learning, Detection & Segmentation

**Transfer Learning**: ImageNet (1.2M images, 18 layers) learns edges, textures, parts, anatomy; use those features, train only new classifier head

**Pretrained Weights API:**
```python
weights = ResNet18_Weights.IMAGENET1K_V1
model = resnet18(weights=weights)
preprocess = weights.transform()  # model's expected pipeline
```

**Linear Probe vs Full Fine-Tune:**
- **Linear Probe** (frozen backbone, train only head): trainable ~0.16%, low risk, lower ceiling
- **Full Fine-Tune** (everything trainable): trainable 100%, medium risk, highest ceiling

**Three Computer Vision Tasks:**
- **Classification**: single label per image ("cat")
- **Object Detection**: bounding boxes + labels ("cat at [x,y,w,h]") – model: Faster R-CNN
- **Segmentation**: pixel-level labels – model: DeepLabV3 (outputs mask per pixel)

**Key Takeaways for Computer Vision:**
1. Pretraining > everything else – fine-tune from pretrained backbone, always
2. The model's preprocessing is part of the model – use weights.transforms()
3. Detection and segmentation are inference-first – don't train from scratch unless you have to

---

## WEEK 7: NLP, TRANSFORMERS & ADVANCED RAG

### 7.1 Text Representations

**The Representation Problem**: Neural network needs fixed-length numeric vectors; text is variable-length string; representation = rule that turns string into vector

**Token types:**
- **Whitespace**: split on spaces ("hello world" → ["hello", "world"])
- **Subword**: split into frequent pieces ("running" → ["run", "##ning"])
- **Character**: every character ("hi" → ["h", "i"])

**Bag-of-Words (BoW)** : Document = multi-set of its tokens; order discarded; becomes sparse vector of length |vocab| with token counts

**TF-IDF**: Re-weights BoW – down-weight tokens that appear in many documents, up-weight rare ones
- TF = frequency of term in document
- IDF = log(total documents / documents containing term)
- TF-IDF = TF × IDF

**Subword Tokenization:**
- **BPE (Byte-Pair Encoding)** – GPT-2 style: merge most-frequent character pairs until vocab full
- **WordPiece** – BERT style: merge pair that maximizes corpus likelihood
- Both produce ~30k-50k token vocabs; gracefully degrade unknown words into known pieces

**Word Embeddings**: Pre-trained encoder maps each token/sentence to real vector (384-768 dimensions); trained so semantically similar inputs land near each other; cosine similarity approximates semantic similarity

**When BoW Wins vs When Embeddings Win:**
- **BoW/TF-IDF**: balanced classification, stable vocabulary, latency-critical (sub-ms), abundant labels
- **Embeddings**: paraphrase-heavy data, retrieval/search, low-data regimes, multi-task setups

### 7.2 Fine-Tuning Transformers

**The Two-Stage Paradigm**: Pretraining (language modeling on massive corpus) → Fine-tuning (adapt to specific task with small labeled dataset)

**What Gets Transferred**: Lower layers = general language understanding (syntax, grammar); higher layers = task-specific patterns

**Model Comparison (AG News)** :

| Model | Parameters | Fine-tune Time (T4) | Macro-F1 |
|-------|------------|---------------------|----------|
| DistilBERT | 66M | ~10 min | ~0.94 |
| BERT-base | 110M | ~20 min | ~0.945 |
| BERT-large | 340M | ~80 min | ~0.95 |

**Training Arguments (Canonical Defaults)** : learning_rate=2e-5, num_train_epochs=2-3, per_device_train_batch_size=16, warmup_ratio=0.1

**Artifacts (save_pretrained)** : config.json (architecture), model.safetensors (weights), tokenizer files, id2label/label2id (human-readable names)

**LoRA (Low-Rank Adaptation)** : Freeze base weights W; learn small matrices A ∈ R^(d×r) and B ∈ R^(r×d); target attention projections (~40M trainable out of 8B = 0.5%); compute gains 5-10×, storage gains 250× (artifact ~1 MB)

### 7.3 NLP Pipelines

**Three NLP Tasks:**

1. **NER (Named Entity Recognition)** : Extract entities (people, orgs, dates, locations); token-level labels; BERT-based model

2. **Zero-Shot Classification**: Uses NLI (Natural Language Inference) – "Does this text entail this label?"; flexible (label set changes without retraining); slower, less accurate than fine-tuned

3. **Summarization**:
   - **Extractive**: pick existing sentences – faithful, fast, static
   - **Abstractive**: generate new sentences – fluent, can synthesize, can hallucinate
   - Modern summarizers (BART, T5, Pegasus) are abstractive

**ROUGE Metric**: Measures n-gram overlap between generated and reference summary; cheap, reproducible, industry standard; weaknesses: rewards extractive copying, blind to negation, doesn't measure faithfulness

**Pipelines as Composable Pieces**: Each pipeline() is callable: text → JSON-serializable dict; chain multiple into one analyze(text) → dict; dict is contract (JSON, easy to log, easy to ship, easy to version)

**Latency Profile:**
- Classification (DistilBERT, fine-tuned): 10-30 ms
- NER (BERT-base): 50-100 ms
- Zero-shot (BART-MNLI): 200-500 ms
- Summarization (DistilBART): 1500-3000 ms

**Production Patterns**: Sequential (today) → per-pipeline batching, async on slow stages, try/except per stage, timeouts (production)

### 7.4 Comparing ML vs DL vs LLM

**Week 7 Progression:**
- Day 1: TF-IDF + Logistic Regression → macro-F1 ~0.905
- Day 2: Fine-tuned DistilBERT → macro-F1 ~0.940
- Day 3: Zero-shot via NLI → macro-F1 ~0.800

**Five Axes That Decide Everything**: Accuracy, latency, cost, maintainability, data requirements

**Model Costs:**
- Classical ML: marginal ≈ 0, amortized tiny
- Deep Learning: marginal ~$0.05/1k, amortized modest
- LLM: marginal ~$0.10-1/1k, amortized zero (no training)

**Latency Percentiles:**
- **p50 (Median)** : typical user experience
- **p95**: worst-case for majority
- **p99**: common production SLA target
- **Mean (Average)** : often misleading – skewed by outliers

**Cascading Classifiers (Tiered System)** :
- Tier 1: TF-IDF + LR – all traffic, near $0, handles ~75% volume
- Tier 2: Fine-tuned DL – low confidence from Tier 1, higher cost, handles ~25%
- Tier 3: LLM zero-shot or human – uncertainty from Tier 2, highest cost, reserved for novel cases

**Confidence Calibration**: A 0.95 confidence prediction should be correct ~95% of the time; reality: fine-tuned transformers overconfident (0.95 score ≈ 85% correct); classical ML's softmax better calibrated

**When to Pick Different Approaches:**
- Latency-critical (<100ms, abundant labels) → fine-tuned DL
- Ultra-fast/stable (sub-ms, balanced classes, stable vocab) → classical ML
- Cold start/dynamic (no labels, low volume, label set changes weekly) → LLM zero-shot
- Efficiency at scale (high volume, mixed difficulty) → cascading

---

## WEEK 8: PRODUCTION DEEP DIVE

### 8.1 Multimodal Fundamentals

**The Multimodal Hypothesis**: There exist instances where P(y|image) ≈ 0.5 AND P(y|text) ≈ 0.5 BUT P(y|image,text) ≈ 1.0 – fusion only helps when interaction carries the signal

**Three Fusion Patterns:**
- **Early**: concatenate raw features before any encoder – rare (backbones expect native input)
- **Late**: run each encoder independently, average logits at end – cheap, parallel, no interaction
- **Intermediate (default)** : each encoder produces embedding, concatenate/attend over them – one small head predicts label

**What Goes Wrong with Naive Concatenation:**
- Head can't tell two sources apart
- Dominant modality causes head to ignore the other
- Larger image norms bias the head

**Making Fusion Robust – Modality Dropout**: During training, randomly zero out one branch's embedding (p=0.1) – never both at once; head learns to predict from one channel when other missing at serve time; reduces peak accuracy in exchange for graceful degradation

**Hateful Memes Dataset**: Facebook AI's ~10k memes, binary classification; adversarially constructed with confounders (same text/different image flips label, same image/different text flips label) – model using only image or only text cannot beat chance on confounder slices

### 8.2 Retraining, Shadow Scoring & Champion/Challenger Gate

**Shadow Scoring**: Champion (v1) serves traffic to users; Challenger (v2) receives same inputs, logs predictions, output NOT returned to users – zero user risk comparison

**The Naive Promotion Gate Is Wrong (3 ways)** :
1. Unpaired comparison ignores that v1 and v2 saw same rows
2. Aggregate lift hides per-segment regressions (Simpson's paradox)
3. Calibration can shift even when accuracy improves

**Paired Tests Beat Unpaired Tests**: For each row, compute v1 and v2 scores side-by-side; bootstrap-resample pairs → mean delta + 95% CI; same data, narrower CI

**Segment-Level Regression Check**: Define segments BEFORE experiment; for each segment, verify v2 non-inferior to v1

**Calibration Delta (The Silent Regressor)** : v2's natural calibration can differ even when ranking same; AUROC identical, cascade gates break silently; fit temperature scaling on both, compare |T_v2/T_v1 - 1| < 0.3

**Drift Trigger to Retrain**: PSI on embedding statistics > 0.2, OR 7-day flagged-rate drift > ε → fire retrain event; anti-flap guard: no second retrain within 72 hours

**Rollback as Code**: After promoting v2, monitor same metrics for 24-48 hours; if live AUROC delta regresses by > ε, auto-revert to v1; monitor is tripwire, silence is success

### 8.3 LLM Fine-tune and Deploy: LoRA, GGUF, Ollama

**The Fine-tuning Problem at LLM Scale**: Full fine-tune of Llama-3-8B requires ~80 GB GPU RAM; T4 has 15 GB → need parameter-efficient methods

**LoRA (Low-Rank Adaptation)** : Freeze base weights W; learn small matrices A ∈ R^(d×r) and B ∈ R^(r×d); target attention projections (~40M trainable out of 8B = 0.5%); inference uses W + (α/r)·B·A merged into single matrix

**4-bit Quantization & Unsloth**: Load base model in 4-bit (~5 GB for Llama-3-8B); Unsloth kernel speeds up training 2-5×

**Chat Template Discipline**: Llama-3 format: `<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|>`; always use `tokenizer.apply_chat_template()` – never hand-roll; mismatched tokenizer = silent garbage

**GGUF (GPT-Generated Unified Format)** : Portable inference format for llama.cpp, Ollama, LM Studio; single binary: quantized weights + tokenizer + chat template + metadata; exported from Unsloth with `model.save_pretrained_gguf()`; size after Q4_K_M: ~5 GB for Llama-3-8B

**Ollama**: Local LLM serving daemon; HTTP API on port 11434, OpenAI-compatible; commands: `ollama run my-model`; Modelfile = Dockerfile-shaped config (GGUF file, system prompt, chat template, parameters)

**Fine-tune-and-ship vs Hosted LLM:**

| Aspect | Fine-tune + Ollama | Hosted LLM |
|--------|-------------------|------------|
| Cost at low volume | One-time training + GPU host | Per-call (~$0.10-1/1k tokens) |
| Cost at high volume | Amortized toward zero | Linear |
| Accuracy on narrow domain | Wins | Loses without RAG |
| Latency | ~50-200ms | ~500-2000ms |
| Privacy | Data stays local | Data leaves network |

### 8.4 How to Be a Great AI Engineer

**What "AI Engineer" Actually Means:**
- **Applied ML Engineer**: ships ML systems – owns model, infrastructure, evaluation, MLOps
- **ML Infrastructure Engineer**: builds training, serving, feature systems
- **Research Engineer**: sits between research and production – pipeline from paper to running system

**The Five Sub-roles:**
- ML Engineer (MLE) – trains, evaluates, ships models
- AI/LLM Engineer – wires prompts, retrieval, tools, evals
- Data Scientist – investigates, runs experiments, builds dashboards
- ML Platform/Infrastructure Engineer – builds training/serving systems
- AI Product Engineer – owns user-facing feature with model inside

**Three Career Arcs:**
- **Depth arc**: world-class at one narrow thing – pay tops out high, mobility harder
- **Breadth arc**: any AI problem from idea to production – steady pay, excellent mobility
- **Product arc**: ML-aware product or engineering management – undervalued path

**The CV That Gets Read:**
- Lead with outcomes, not technologies ("Reduced inference latency by 60%")
- Include concrete numbers in every bullet
- Strict page limits (1 page junior, 2 max senior)
- Provide one live link a stranger can run in 5 minutes

**The Interview Loop:**
- Technical phone screen (30-90 min): ML concepts, production readiness
- System design (45-90 min): data flow, not just models
- Take-home (4-12 hours): working baseline + great README
- Behavioural (30-60 min): three deep, real-world stories

**What Great Engineers Do Better:**
- Write before building (one-page design doc)
- Define non-scope explicitly
- Invest in tooling (automate repetitive tasks)
- Read more than write (senior engineer's secret – having read 100× more code)
- Flag bad news early (Day 1 vs Day 5)

**The New Craft Skill (AI-Assisted Development)** : AI-assisted dev (Cursor, Claude Code, Copilot) is table stakes; the trap = shipping code you cannot debug; pattern that works = agent drafts, you read every line, delete what you don't understand; **your edge in 2026: "I can read what the agent wrote and find the bug it hid"**

**Building a Public Footprint**: Write now, not when senior (seniors have no time); personal blog with 5-10 deep posts > 100 LinkedIn updates; what works = project write-ups with runnable artifacts, honest post-mortems; what kills credibility = AI-generated posts, motivational rephrasing, daily engagement bait

**Three Habits That Compound:**
1. Ship one thing publicly every month (repo, post, demo)
2. Maintain one weak tie outside your company (talk monthly)
3. Spend 1-2 hours/week on something you are bad at

---

## WEEK 8 – ADVANCED PRODUCTION PATTERNS (Continued)

### 8.5 State & Correctness: Transactions, Outbox, Idempotency

**Three Things to Internalize:**
1. Make writes atomic – related writes commit together or not at all
2. Never dual-write – two systems with no shared transaction will disagree
3. Assume it arrives twice – at-least-once is default, design for duplicates

**Transactions as Correctness**: All-or-nothing guarantee – every write inside happens or none do; bank transfer example: debit A + credit B in one transaction; race condition fix: use `UPDATE balance = balance + 1` (atomic) instead of SELECT then UPDATE

**The Dual-Write Trap:**
```python
# BAD – crash between DB commit and publish
with conn.transaction():
    orders.insert(order)  # committed to Postgres
publish("order.created", order)  # crash HERE → DB has order, queue never heard
```
**Cannot reorder your way out** – both orderings have a failure window

**The Outbox Pattern:**
```python
# GOOD – event committed atomically with data
with conn.transaction():
    orders.insert(order)
    outbox.insert(topic="order.created", payload=order.json())
# Separate relayer drains table after, at-least-once
```
One transaction covers data + intent to publish; queue can be down – event safe in Postgres

**The Catch: At-Least-Once**: Relayer crashes after publish but before mark_published → republishes on restart; duplicates guaranteed by design; we chose "never lost" over "never repeated"

**Idempotency: Make Duplicates a No-Op:**
```python
def handle(event):
    if processed.exists(event.id):  # dedupe table
        return
    with conn.transaction():
        fulfill(event)
        processed.insert(event.id)  # same transaction
```
Dedupe insert and work share one transaction; without this, republished event charges/ships twice

**You Need Both**: Outbox alone → reliable duplicates; Idempotency alone → reliable data loss; Outbox + Idempotency = never lost + harmless repeats

### 8.6 Guardrails for LLMs with NeMo Guardrails

**The Problem – LLM with no guardrails**: Jailbreaks & injection ("Ignore your instructions" – and it complies); data leaks (spits out secrets, PII); hallucination (invents facts); off-topic/brand risk (medical or legal advice)

**What is NeMo Guardrails?**: NVIDIA open-source toolkit for programmable safety and control layers; sits between user and LLM – screens both directions; rules live in config, not buried in code; model-agnostic

**Five Kinds of Rails:**
- **Input rails** (focus today): screen user message before LLM
- **Dialog rails**: steer conversation along allowed paths
- **Retrieval rails** (focus today): screen retrieved context (RAG chunks)
- **Output rails** (focus today): screen LLM response before user sees
- **Execution rails**: guard tool/action calls

**How a Request Flows**: User → Input Rail → Retrieval Rail → LLM → Output Rail → Reply (any rail can short-circuit – LLM may never be called)

**Anatomy of a Guardrails Config:**
```
config/
├── config.yml      # which models + which rails active
├── prompts.yml     # prompts for self-check rails
└── rails/*.co      # Colang flows (custom rails)
```

**Input Rails**: Triggered the moment user message arrives; catches jailbreaks, off-topic, PII, toxic/abusive; activate with `rails.input.flows: [self check input, jailbreak detection heuristics]`; `self check input` = LLM call asking "does this break policy?"; blocked message returns configurable refusal (LLM never called)

**Output Rails**: Triggered after LLM responds – last line of defense; activate with `rails.output.flows: [self check output, self check facts, mask sensitive data on output]`; `self check facts` = grounded in retrieved context?; PII masking uses Presidio to redact PERSON, EMAIL, CREDIT_CARD

**Retrieval Rails (for RAG)** : Screen chunks before they reach the prompt; risks: sensitive chunks, poisoned context, ungrounded answers; activate with `rails.retrieval.flows: [check retrieval sensitive data]`

**Configuration Example (RAG Chatbot Baseline)** :
```yaml
rails:
  input:
    flows: [self check input, jailbreak detection heuristics]
  retrieval:
    flows: [check retrieval sensitive data]
  output:
    flows: [self check output, self check facts, mask sensitive data on output]
```

**Three Ways to Run:**
- **Library**: import LLMRails in Python – simplest, tightly coupled
- **Server**: run guardrails server, call over HTTP – language-agnostic
- **Sidecar**: dedicated microservice – clean separation, scales on its own

**Rails Aren't Free**: Every LLM-based rail = another model call (4× rails ≈ 4× round-trips); use small/cheap models for rails (gpt-4o-mini); run independent rails in parallel; short-circuit with cheap regex/heuristics first

**Common Pitfalls**: Over-blocking (aggressive rails frustrate users); weak prompts = weak rails; not a silver bullet; latency creep

### 8.7 Spec-Driven Development with GitHub Spec Kit

**The Problem with Vague Prompts**: "Build me a travel planner" – agent invents stack, data model, scope; problem isn't agent – it's that nobody wrote down what "right" meant

**The Mental Shift**: Code-first = intent lives in head, code is only truth, docs rot; Spec-first = intent written down, spec is truth, code follows spec

**What is Spec Kit?**: GitHub open-source toolkit; adds structured slash commands to Claude, Copilot, Gemini (30+ agents); ships full Spec → Plan → Tasks → Implement loop with templates

**The Seven Commands:**
1. `/speckit.constitution` – write non-negotiable principles the agent must follow
2. `/speckit.specify` – describe WHAT and WHY (not how) – user stories + acceptance criteria
3. `/speckit.clarify` – quality gate – asks up to 5 questions about underspecified areas
4. `/speckit.plan` – decide HOW – tech stack, architecture, data model
5. `/speckit.tasks` – break plan into small, ordered, testable tasks
6. `/speckit.analyze` – second gate – checks whole artifact set hangs together
7. `/speckit.implement` – agent writes code against spec and plan

**The Workflow**: constitution → specify → clarify → plan → tasks → analyze → implement

**Enforce in CI: No Spec, No Merge** – GitHub Action that fails PR without spec.md

**When Spec Kit Earns Its Keep**: real features with stakes and edge cases; work an agent will implement; anything multiple people must agree on; projects that outlive one coding session

**Skip It When**: 10-line throwaway script; pure exploration; genuinely don't know goal yet; tiny fixes where spec > change

### 8.8 Structuring Systems: Monoliths, Microservices & Clean Boundaries

**The Trap**: Read how giant companies build software – headline is always "split everything"; copy it – chop small app into many pieces before you need to; result = slower to build, more fragile, harder to change

**The Key Intuition: Rooms vs Letters**: Same program = talking in same room (instant, reliable); another service = mailing a letter (slower, needs address, can get lost)

**Three Shapes:**
- **Monolith**: one program does everything
- **Microservices**: many small separate programs, talk over network
- **Modular Monolith**: one program, clean inner walls, still one app

**The Honest Tradeoff**: Modular monolith = underrated middle ground – most benefit of clean separation, little operational pain

**When to Actually Split:**
1. Needs far more horsepower (resource-hungry piece)
2. Needs its own release schedule (different rhythm)
3. Must be isolated for safety (sensitive)
4. Written in different language

**Three Real Cases:**
1. **Shopify/Instagram**: started as monolith, shipped fast – correct early choice
2. **Amazon/Netflix**: forced to split by scale and team size
3. **Segment**: split too early, operational overhead overwhelmed, merged back – famous walk-back

**The Lesson**: There is no universally correct architecture. There's the right one for your constraints, right now.

**Keeping the Inside Clean (Clean Architecture)** : Core logic (business rules) should not care which tool; outside tools point IN to core; core never points out at specific brand

**The Plug-Shape Idea (Interface)** :
```python
from typing import Protocol

class PaymentGateway(Protocol):
    def charge(self, amount_cents: int, token: str) -> str: ...

class StripeGateway:
    def charge(self, amount_cents, token):
        return "ch_live_123"

class FakeGateway:
    def charge(self, amount_cents, token):
        return "fake_ch_123"

class Checkout:
    def __init__(self, payments: PaymentGateway):
        self.payments = payments
```

**Why Interfaces Are Worth It**: The fake is the whole point – test without real thing, real cost, real network; switching providers later = write one new "device" – not edit whole app

**The Rule That Stops Over-Building**: If there's only ever one version, and a test fake wouldn't help – don't add a plug shape. Just use the thing directly.

---

## GITHUB REPOSITORIES

| Repo | Purpose |
|------|---------|
| `github.com/hasankanaan26/Unit-Testing-Python` | Beginner-friendly unit testing, VS Code Test Explorer |
| `github.com/hasankanaan26/evals-python` | Eval-driven development implementation |
| `github.com/hasankanaan26/advanced-rag-architectures` | Advanced RAG techniques (w7s1-advanced-rag-tagalong) |
| `github.com/hasankanaan26/Advanced-Agentic-AI` | Full agent implementation from Week 4-5 |

---

## SUMMARY STATISTICS

| Category | Topics |
|----------|--------|
| Weeks 1-5 (ML, MLOps, RAG, Agentic AI) | ~366 |
| Week 6 (Deep Learning, CV, Eval-Driven Dev) | ~85 |
| Week 7 (NLP, Transformers, Advanced RAG, GraphRAG, RAGAS) | ~85 |
| Week 8 (Multimodal, Retraining, LoRA/GGUF/Ollama, Career, Transactions, Guardrails, Spec Kit, Architecture) | ~80 |
| **GRAND TOTAL** | **~616 topics** |

---

*This document contains the complete technical curriculum of the 8-week AI Engineering Bootcamp. Every topic from all 62 files is documented above.*


Classical ML – regression, classification, feature engineering, feature selection, hyperparameter tuning, experiment tracking (MLflow)

Deep Learning & Computer Vision – neural networks, backpropagation, CNNs, transfer learning, object detection (Faster R-CNN), segmentation (DeepLabV3), PyTorch

NLP & Transformers – text representations (BoW, TF-IDF, word embeddings), subword tokenization (BPE, WordPiece), fine-tuning DistilBERT/BERT, LoRA, zero-shot classification, NER, summarization, ROUGE

RAG (Full Stack) – naive RAG → parent-document retrieval → multi-vector retrieval → HyDE → multi-query → step-back → query decomposition → routing → GraphRAG → cross-encoder re-ranking → RAG evaluation with RAGAS (context precision/recall, faithfulness, response relevancy)

Agentic AI – tool calling, ReAct pattern, LangGraph, human-in-the-loop, multi-agent architectures (supervisor, hierarchical, swarm), memory & persistence, checkpoints, tracing, agent software engineering (mocking LLMs, snapshot testing, prompt versioning)

MLOps & Production – model registry (MLflow), semantic versioning, input validation (Pydantic), observability (four golden signals, PSI, chi-square, drift detection), shadow scoring, champion/challenger gate, retraining loops, rollback as code

Production Patterns – queues with Redis (idempotency, DLQ, retries, worker scaling, lease timeout), outbox pattern, dual-write trap, transactions, idempotency

LLM Deployment – LoRA fine-tuning, 4-bit quantization (Unsloth), GGUF, Ollama local serving

Prompt Engineering – zero-shot, few-shot, chain-of-thought, role prompting, system/user prompts, structured output, chaining, temperature, delimiters, negative prompting, injection defense, ReAct agents

Guardrails – NeMo Guardrails (input/output/retrieval rails)

Spec-Driven Development – GitHub Spec Kit (constitution, specify, clarify, plan, tasks, analyze, implement)

System Architecture – monoliths vs microservices vs modular monolith, clean architecture, interfaces/Protocols

Infrastructure – Docker, AWS (S3, Lambda, Bedrock, Polly, SES), FastAPI (routers, dependencies, validators)

Eval-Driven Development – tests vs evals, dataset curation (golden, curated, adversarial), LLM-as-judge (calibration, biases), production logging, trace IDs, error handling, fallback chains

Multimodal AI – two-branch fusion (early/late/intermediate), modality dropout, Hateful Memes dataset

Career & Software Engineering – hiring loops, CV writing, public footprint, reading code vs papers, AI-assisted development discipline