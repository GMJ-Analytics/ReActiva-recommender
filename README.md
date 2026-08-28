# Reactiva — Customer Reactivation Recommendation System

## Overview

Reactiva is a recommendation system designed to identify customers who may have become inactive and recommend products they are likely to purchase when they return.

The system uses historical customer purchase behavior to identify inactive customers and generate personalized product recommendations.

The primary recommendation pipeline uses a **Gradient Boosting classifier** to predict the product category that an inactive customer is most likely to purchase. The system then recommends the most popular products within that predicted category.

The project also evaluates alternative recommendation approaches using a shared time-based backtesting framework.

---

# Recommendation Pipeline

The production recommendation process follows this structure:

```text
Historical Customer Purchases
            │
            ▼
Build Customer Features
            │
            ▼
Identify Active and Inactive Customers
            │
            ▼
Train Gradient Boosting Model
            │
            ▼
Predict Most Likely Product Category
            │
            ▼
Select Popular Recent Items
Within the Predicted Category
            │
            ▼
Top-K Product Recommendations
```

The recommendation process can be summarized as:

```text
Customer History
      ↓
Customer Features
      ↓
Gradient Boosting
      ↓
Predicted Category
      ↓
Popular Items in Category
      ↓
Recommendations
```

---

# Inactive Customer Identification

Customers are considered potential inactive customers when:

1. They have historical purchase activity.
2. They have not made a purchase during the configured inactivity period.

The system divides the available data into two periods:

```text
Historical Window
        │
        ├── Used to build customer features
        │
        └── Used to identify customers with historical activity

Recent Window
        │
        ├── Used to identify currently active customers
        │
        ├── Used to create category labels
        │
        └── Used to determine currently popular products
```

Customers who appear in the historical window but do not appear in the recent window are considered inactive candidates.

---

# Gradient Boosting Recommender

The main recommendation model uses a `GradientBoostingClassifier`.

The model is trained using active customers.

For each active customer:

```text
Historical Customer Behavior
        ↓
Customer Features
        ↓
Gradient Boosting
        ↓
Most Frequent Category
During the Recent Window
```

The predicted category is then used to generate product recommendations.

For an inactive customer:

```text
Historical Behavior
        ↓
Customer Features
        ↓
Gradient Boosting
        ↓
Predicted Product Category
        ↓
Top-K Popular Recent Items
Within That Category
```

This allows the system to generate recommendations that are personalized at the category level.

---

# Customer Features

Customer features are built from historical purchase behavior.

The feature representation may include:

* Purchase frequency by category
* Total purchases
* Recency of the customer's last purchase
* Other historical behavioral signals

The objective is to represent each customer using only information available before the recommendation period.

This prevents future purchase information from being used during training.

---

# Popularity-Based Recommendation

A global popularity model is used as a baseline.

The popularity model recommends the same Top-K most frequently purchased items to all evaluated customers.

```text
Historical / Recent Purchase Data
            ↓
Calculate Item Popularity
            ↓
Rank Items by Frequency
            ↓
Top-K Most Popular Items
            ↓
Same Recommendations for All Customers
```

The popularity model is important because it provides a strong baseline against which personalized recommendation models can be compared.

A more complex model is only useful if it provides sufficient additional value compared with this baseline.

---

# GBoost + Popularity Blend

An experimental hybrid recommendation approach combines:

* Personalized category-based recommendations from Gradient Boosting.
* Globally popular products.

For example:

```text
GBoost Recommendations:
[A, B, C]

Global Popularity:
[D, E]

Final Recommendation List:
[A, B, C, D, E]
```

Duplicate items are removed.

If duplicates reduce the number of recommendations below `K`, additional globally popular items are used to fill the recommendation list.

This experiment allows the system to evaluate the trade-off between:

```text
Personalization
        +
Popularity Accuracy
        +
Catalog Diversity
```

Different blending ratios can be evaluated, such as:

```text
4 GBoost + 1 Popularity
3 GBoost + 2 Popularity
2 GBoost + 3 Popularity
1 GBoost + 4 Popularity
0 GBoost + 5 Popularity
```

---

# Evaluation Framework

All recommendation models are evaluated using the same **time-based backtesting framework**.

The data is divided into three conceptual periods:

```text
Training Window
      ↓
Recent Window
      ↓
Future Holdout Window
```

### Training Window

The training window contains historical customer behavior.

It is used to:

* Build customer features.
* Train recommendation models.
* Build customer-item relationships.
* Define the long-tail catalog.

### Recent Window

The recent window is used to:

* Identify active customers.
* Identify potentially inactive customers.
* Create target labels for the Gradient Boosting model.
* Identify currently popular products.

### Future Holdout Window

The future window is not used to train the models.

It contains the future purchases of customers who were previously identified as inactive.

These purchases are used as the ground truth.

The common evaluation question is:

> Can information available before an inactive customer returns help predict which items that customer will purchase later?

---

# Shared Model Evaluation

All models are evaluated at the same level:

```text
Customer
    │
    ▼
Top-K Recommended Items
    │
    ▼
Compare With
Actual Future Purchases
```

This ensures that different recommendation approaches are evaluated under the same framework.

The models can differ internally, but their final output is evaluated in the same way:

```text
Recommended Items
        vs
Actual Future Purchases
```

---

# Ranking Metrics

## Precision@K

Precision measures how many recommended items were actually purchased.

```text
Precision@K =
Relevant Recommended Items
──────────────────────────
Total Recommended Items
```

A high Precision@K means that a larger proportion of the recommendations were relevant.

---

## Recall@K

Recall measures how many of the customer's actual future purchases were recovered by the recommendation list.

```text
Recall@K =
Relevant Recommended Items
────────────────────────
Actual Purchased Items
```

For example:

```text
Recommended:
[A, B, C, D, E]

Actually Purchased:
[B, D, F]
```

The model successfully recovered:

```text
[B, D]
```

Therefore:

```text
Recall@5 = 2 / 3
```

Recall is particularly important when evaluating whether the recommender can recover items the customer actually buys.

---

## Hit Rate@K

Hit Rate measures whether the recommendation list contains at least one item that the customer actually purchased.

```text
Hit Rate@K =

1 → At least one recommendation was purchased.

0 → None of the recommendations were purchased.
```

The final Hit Rate is the average across evaluated customers.

---

## NDCG

Normalized Discounted Cumulative Gain evaluates the ranking quality of the recommendations.

Relevant items that appear higher in the recommendation list receive greater value.

For example:

```text
Position 1 → Higher importance
Position 2 → Slightly lower importance
Position 3 → Lower importance
```

Therefore, NDCG measures not only whether relevant items were recommended, but also whether they were ranked near the top of the list.

---

## MAP

Mean Average Precision evaluates the precision of the recommendation list at the positions where relevant items appear.

MAP rewards models that place relevant recommendations earlier in the ranking.

Together with NDCG, MAP provides additional information about recommendation ranking quality.

---

# Long-Tail Evaluation

Overall Recall can favor models that repeatedly recommend popular products.

To evaluate whether the models can also recover less frequently purchased products, the system includes long-tail metrics.

The long-tail catalog is defined using the training data.

Items are ranked according to purchase frequency, and the popular head of the catalog is defined using an **80% cumulative purchase-share cutoff**.

Items outside that popular head are considered long-tail items.

```text
Item Popularity Distribution

Highly Popular Items
        │
        ▼
80% Cumulative Purchase Share
        │
        ├── Popular Head
        │
        └── Long-Tail Items
```

---

## Long-Tail Precision

Measures the proportion of recommended items that are both:

* Relevant.
* Long-tail items.

A high value indicates that the recommender successfully recommends less-popular items that customers actually purchase.

---

## Long-Tail Recall

Measures the model's ability to recover long-tail items that customers actually purchased.

```text
Long-Tail Recall =
Relevant Long-Tail Recommendations
─────────────────────────────────
Actual Long-Tail Purchases
```

---

## Long-Tail Hit Rate

Measures whether the recommender successfully recommends at least one relevant long-tail item to a customer who purchases long-tail products.

---

## Long-Tail Share

Measures the proportion of recommendation slots occupied by long-tail items.

For example:

```text
Recommended Items:

[A, B, C, D, E]

Long-Tail Items:

[C]
```

Then:

```text
Long-Tail Share = 1 / 5 = 20%
```

This metric measures how much exposure the recommender gives to less-popular products.

---

## Long-Tail Catalog Coverage

Measures the proportion of the available long-tail catalog that appears at least once in the recommendations.

For example:

```text
Available Long-Tail Items:
[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

Long-Tail Items Recommended:
[1, 3, 5]

Long-Tail Catalog Coverage:

3 / 10 = 30%
```

A higher catalog coverage indicates that the model recommends a broader range of long-tail products.

---

# Average Score

The Average Score provides an aggregate summary of predictive and ranking performance.

It is calculated as the mean of:

* Precision
* Recall
* Hit Rate
* Long-Tail Precision
* Long-Tail Recall
* Long-Tail Hit Rate
* NDCG
* MAP

The following metrics are excluded from the Average Score:

* Long-Tail Share
* Long-Tail Catalog Coverage
* Sparsity

These metrics are treated separately because they describe recommendation distribution and characteristics of the system rather than direct predictive accuracy.

---

# Sparsity

Sparsity measures how many possible user-item interactions are empty.

A highly sparse interaction matrix means that customers have interacted with only a small proportion of the available catalog.

```text
User × Item Matrix

        Item A  Item B  Item C  Item D

User 1     1       0       0       1

User 2     0       1       0       0

User 3     0       0       1       0
```

Most cells are empty, which indicates a sparse recommendation problem.

Sparsity is reported as a diagnostic characteristic of the dataset and recommendation environment.

---

# Learning Curve Experiments

Learning curves are used to evaluate how model performance changes as more historical training data becomes available.

The experiment uses progressively larger portions of the training history:

```text
20%
40%
60%
80%
100%
```

The future evaluation data remains fixed.

The only experimental variable is the amount of historical training data available to the model.

```text
20% Historical Data
        ↓
Train Models
        ↓
Evaluate on Same Future Holdout

40% Historical Data
        ↓
Train Models
        ↓
Evaluate on Same Future Holdout

...

100% Historical Data
        ↓
Train Models
        ↓
Evaluate on Same Future Holdout
```

Learning curves can be evaluated using:

* Recall@5
* Long-Tail Recall@5

These experiments help determine whether additional historical data improves the ability of each model to recover future purchases and long-tail purchases.

---

# Models Evaluated

The project evaluates the following recommendation approaches:

### Gradient Boosting

```text
Customer History
        ↓
Customer Features
        ↓
Gradient Boosting
        ↓
Predicted Category
        ↓
Popular Items Within Category
```

### Content-Based Recommendation

Uses customer or product characteristics to generate recommendations based on similarity.

### User-Based Collaborative Filtering

Uses similarities between customers to identify products purchased by similar users.

### Popularity Baseline

Recommends the globally most popular items.

### GBoost + Popularity Blend

Combines category-based recommendations from GBoost with globally popular items.

---

# Model Selection

Model selection is based on the business objective rather than a single metric.

If the primary objective is:

```text
Maximize Future Purchase Recovery
```

then Recall, Hit Rate, NDCG, and MAP are particularly important.

If the objective includes:

```text
Personalization
        +
Product Discovery
        +
Long-Tail Exposure
```

then Long-Tail Recall, Long-Tail Share, and Long-Tail Catalog Coverage become important considerations.

A simple popularity model may outperform more complex personalized models on overall purchase recovery.

However, a popularity model can recommend the same products to every customer and may provide little or no long-tail exposure.

The final recommendation strategy should therefore balance:

```text
Predictive Accuracy
        +
Personalization
        +
Ranking Quality
        +
Long-Tail Recovery
        +
Catalog Coverage
```

---

# Production Workflow

The production workflow is:

```text
Transaction Data
      ↓
Load Dataset
      ↓
Identify Historical and Recent Windows
      ↓
Identify Inactive Customers
      ↓
Build Customer Features
      ↓
Train Gradient Boosting Classifier
      ↓
Predict Customer Categories
      ↓
Generate Top-K Recommendations
      ↓
Store Predictions
      ↓
Application Interface
```

Predictions can be persisted for later use so that the recommendation interface does not need to retrain the model for every user request.

---

# Project Goal

The objective of Reactiva is to explore whether historical customer behavior can be used to generate relevant recommendations for customers who become inactive and later return.

The project compares multiple recommendation strategies using the same time-based future holdout framework.

The final evaluation considers not only whether recommended products match future purchases, but also:

* Ranking quality.
* Personalization.
* Long-tail performance.
* Product discovery.
* Catalog coverage.
* Data sparsity.

This provides a broader evaluation of recommendation quality than relying on a single metric.
