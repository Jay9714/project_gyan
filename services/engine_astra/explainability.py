
import shap
import pandas as pd
import numpy as np

def explain_prediction(model, X_sample):
    """
    Generates SHAP values for a single prediction instance.
    Returns: Text explanation of top drivers.
    """
    try:
        # Create Explainer (TreeExplainer works for XGB, CatBoost, LightGBM, RF)
        # Note: If 'model' is a StackingRegressor, we might need to access the base estimators.
        # But commonly we explain the strongest base model (e.g. XGBoost).
        # OR we can use KernelExplainer for black-box (slow).
        
        # Determining model type logic:
        explainer = None
        
        # If it's a specific tree model:
        if hasattr(model, 'feature_importances_'): 
             explainer = shap.TreeExplainer(model)
        
        if not explainer: return "Model type not supported for fast SHAP explanation."
        
        shap_values = explainer.shap_values(X_sample)
        
        # If Multi-output, take first
        if isinstance(shap_values, list): shap_values = shap_values[0]
        
        # Get Feature Names
        feature_names = X_sample.columns.tolist()
        
        # Get Top 3 Positive and Negative Drivers
        # shap_values[0] is array of shape (features,)
        vals = shap_values[0] if len(shap_values.shape) > 1 else shap_values
        
        feature_importance = pd.DataFrame(list(zip(feature_names, vals)), columns=['col_name','feature_importance_vals'])
        
        # Calculate Percentage Contribution (Relative to Total Impact)
        total_impact = np.sum(np.abs(vals)) + 1e-9
        feature_importance['pct'] = (feature_importance['feature_importance_vals'] / total_impact) * 100
        
        feature_importance.sort_values(by=['feature_importance_vals'], ascending=False, inplace=True)
        
        top_drivers = feature_importance.head(3)
        # For negative, we want the most negative, which are at the bottom
        bottom_drivers = feature_importance.tail(2)
        
        explanation = "key_factors: "
        features_list = []
        
        for index, row in top_drivers.iterrows():
            if row['feature_importance_vals'] > 0:
                features_list.append(f"{row['col_name']} (+{row['pct']:.1f}%)")
                
        for index, row in bottom_drivers.iterrows():
             if row['feature_importance_vals'] < 0:
                features_list.append(f"{row['col_name']} ({row['pct']:.1f}%)")
                
        return ", ".join(features_list)
        
    except Exception as e:
        print(f"SHAP Error: {e}")
        return "Could not generate explanation."
