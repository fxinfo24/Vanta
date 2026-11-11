"""
Report Generator
Generates professional HTML/PDF dossiers from intelligence data.
Uses Jinja2 for templating.
"""

import os
import json
import logging
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from typing import Dict, Any

logger = logging.getLogger(__name__)

class DossierReportGenerator:
    """Generates professional intelligence reports"""
    
    def __init__(self, template_dir: str = "app/web/templates/reports"):
        self.template_dir = template_dir
        # Ensure template dir exists
        os.makedirs(template_dir, exist_ok=True)
        
        self.env = Environment(
            loader=FileSystemLoader(os.path.dirname(os.path.abspath(__file__)) + "/../../web/templates")
        )
        
    def generate_html_report(self, report_data: Dict[str, Any]) -> str:
        """
        Generate a standalone HTML dossier.
        """
        try:
            # We'll use a string template if file doesn't exist to avoid dependency issues
            template = self._get_default_template()
            
            # Enrich data for display
            display_data = self._prepare_data_for_display(report_data)
            
            return template.render(data=display_data, generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"))
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return f"<h1>Error generating report</h1><p>{str(e)}</p>"

    def _prepare_data_for_display(self, data: Dict) -> Dict:
        """Format data for easier rendering with strict null safety"""
        if not data:
            data = {}
            
        def safe_get(d, *keys, default=None):
            """Deep get"""
            for key in keys:
                if isinstance(d, dict):
                    d = d.get(key, {})
                else:
                    return default
            return d if d else default

        # Safe defaults for all sections
        profile = data.get("profile_info") or {}
        meta = data.get("metadata") or {}
        behavior = data.get("behavioral_profile") or {}
        raw = data.get("raw", {}) or {}
        # Quick scans now write `content`; older stored dossiers used `recent_content`.
        content_items = raw.get("content") or raw.get("recent_content") or []

        return {
            "meta": {
                "profile_id": meta.get("profile_id", "Unknown"),
                "platform": meta.get("platform", "Unknown"),
                "analysis_hash": meta.get("analysis_hash", "N/A"),
                "collection_mode": meta.get("collection_mode", "standard")
            },
            "profile": {
                "username": profile.get("username", "Unknown"),
                "display_name": profile.get("display_name", "Unknown Target"),
                "bio": profile.get("bio", "No bio available."),
                "followers": profile.get("followers", 0),
                "following": profile.get("following", 0),
                "posts": profile.get("posts", 0),
                "profile_image_url": profile.get("profile_image_url", ""),
                "is_verified": profile.get("is_verified")
            },
            "summary": data.get("executive_summary") or "Executive summary generation failed or data is unavailable.",
            "psych": data.get("content_analysis", {}).get("personality_traits") or data.get("content_analysis", {}).get("psychological_profile", {}),
            "beliefs": data.get("belief_system") or {},
            "consumer": data.get("consumer_profile") or {},
            "auth": data.get("authenticity") or {},
            "connected_accounts": data.get("connected_accounts") or [],
            "behavior": behavior,
            "content": content_items[:5], # Top 5 items
            "raw": data
        }

    def _get_default_template(self):
        """Returns a Jinja2 Template object with default layout"""
        html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>VANTA Intelligence Dossier: {{ data.profile.username if data.profile and data.profile.username else 'Unknown Profile' }}</title>
    <style>
        :root { --primary: #0f172a; --accent: #3b82f6; --danger: #ef4444; --bg: #f8fafc; --text: #334155; }
        
        /* Print Optimization */
        @media print {
            body { background: white; padding: 0; font-size: 11pt; }
            .no-print { display: none !important; }
            .section { break-inside: avoid; border: 1px solid #ddd; box-shadow: none; }
            .page-break { page-break-before: always; }
        }

        body { 
            font-family: 'Inter', system-ui, -apple-system, sans-serif; 
            line-height: 1.6; 
            color: var(--text); 
            max-width: 900px; 
            margin: 0 auto; 
            padding: 40px; 
            background: var(--bg); 
        }
        
        .header { 
            border-bottom: 2px solid #e2e8f0; 
            padding-bottom: 20px; 
            margin-bottom: 30px; 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
        }
        .logo { 
            font-weight: 900; 
            font-size: 28px; 
            color: var(--primary); 
            letter-spacing: -1px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .logo span { color: var(--accent); }
        
        .profile-card { 
            background: white; 
            padding: 30px; 
            border-radius: 12px; 
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); 
            display: flex; 
            gap: 25px; 
            margin-bottom: 30px; 
            align-items: flex-start;
        }
        .avatar { 
            width: 120px; 
            height: 120px; 
            border-radius: 16px; 
            object-fit: cover; 
            background: #e2e8f0; 
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
            flex-shrink: 0;
        }
        .profile-info h1 { margin: 0 0 5px 0; font-size: 28px; color: var(--primary); }
        .profile-info .handle { font-family: monospace; color: var(--accent); font-size: 16px; }
        .stats { display: flex; gap: 20px; margin-top: 15px; font-size: 14px; color: #64748b; background: #f8fafc; padding: 10px 15px; border-radius: 8px; }
        
        .section { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin-bottom: 25px; }
        h2 { color: var(--primary); font-size: 20px; border-left: 4px solid var(--accent); padding-left: 15px; margin-top: 0; margin-bottom: 20px; }
        h3 { font-size: 16px; color: #475569; margin-bottom: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; font-size: 12px; }
        
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 25px; }
        
        .tag { display: inline-block; padding: 4px 10px; background: #f1f5f9; color: #475569; border-radius: 6px; font-size: 12px; margin-right: 6px; margin-bottom: 6px; border: 1px solid #e2e8f0; }
        .tag.brand { background: #e0f2fe; color: #0369a1; border-color: #bae6fd; }
        
        .bar-container { background: #f1f5f9; height: 8px; border-radius: 4px; overflow: hidden; margin-top: 6px; }
        .bar-fill { height: 100%; background: var(--accent); border-radius: 4px; }
        
        .risk-badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 6px;
            font-weight: bold;
            font-size: 14px;
        }
        .risk-low { background: #dcfce7; color: #166534; }
        .risk-medium { background: #fef9c3; color: #854d0e; }
        .risk-high { background: #fee2e2; color: #991b1b; }

        .content-table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .content-table th { text-align: left; padding: 10px; background: #f8fafc; color: #64748b; border-bottom: 1px solid #e2e8f0; }
        .content-table td { padding: 10px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
        .content-table tr:last-child td { border-bottom: none; }

        .print-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: var(--primary);
            color: white;
            padding: 12px 24px;
            border-radius: 50px;
            text-decoration: none;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            font-weight: bold;
            transition: transform 0.2s;
            cursor: pointer;
            border: none;
        }
        .print-btn:hover { transform: translateY(-2px); }

        .footer { 
            margin-top: 60px; 
            border-top: 1px solid #e2e8f0; 
            padding-top: 25px; 
            font-size: 12px; 
            color: #94a3b8; 
            text-align: center; 
            font-family: monospace;
        }
    </style>
    <script>
        function printReport() {
            window.print();
        }
    </script>
</head>
<body>
    <button onclick="printReport()" class="print-btn no-print">🖨️ Print / Save as PDF</button>

    <div class="header">
        <div class="logo">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="#3B82F6"/>
                <path d="M2 17L12 22L22 17" stroke="#3B82F6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M2 12L12 17L22 12" stroke="#3B82F6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            VANTA <span>INTELLIGENCE</span>
        </div>
        <div style="text-align: right">
            <div style="font-size: 14px; color: var(--text);"><strong>TARGET DOSSIER</strong></div>
            <div style="font-size: 12px; color: #64748b; font-family: monospace;">ID: {{ data.meta.profile_id or data.profile.username or 'UNKNOWN' }}</div>
            <div style="font-size: 12px; color: #64748b;">Generated: {{ generated_at }}</div>
        </div>
    </div>

    <!-- PROFILE OVERVIEW -->
    <div class="profile-card">
        {% if data.profile.profile_image_url %}
        <img src="{{ data.profile.profile_image_url }}" class="avatar" alt="Profile" onerror="this.style.display='none'">
        {% else %}
        <div class="avatar" style="display: flex; align-items: center; justify-content: center; font-size: 40px; color: #94a3b8;">?</div>
        {% endif %}
        <div class="profile-info" style="flex: 1">
            <h1>{{ data.profile.display_name or data.profile.username or 'Unknown Target' }}</h1>
            <div class="handle">@{{ data.profile.username or 'unknown' }}</div>
            
            {% if data.profile.bio %}
            <p style="margin: 15px 0; color: #475569;">{{ data.profile.bio }}</p>
            {% endif %}

            <div class="stats">
                <span><strong>{{ "{:,}".format(data.profile.followers|int) if data.profile.followers else '-' }}</strong> Followers</span>
                <span><strong>{{ "{:,}".format(data.profile.posts|int) if data.profile.posts else '-' }}</strong> Posts</span>
                <span>Platform: <strong style="text-transform: capitalize">{{ data.meta.platform or 'Unknown' }}</strong></span>
            </div>
            
            {% if data.profile.is_verified %}
            <div style="margin-top: 10px; color: #059669; font-weight: bold; font-size: 12px; display: flex; align-items: center; gap: 5px;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>
                VERIFIED IDENTITY
            </div>
            {% endif %}
        </div>
    </div>

    <!-- EXECUTIVE SUMMARY -->
    <div class="section" style="border-left: 4px solid var(--accent);">
        <h2>Executive Intelligence Summary</h2>
        <p style="font-size: 16px; line-height: 1.8; color: #334155;">{{ data.summary }}</p>
    </div>

    <div class="grid">
        <!-- AUTHENTICITY & RISK -->
        <div class="section">
            <h2>🛡️ Authenticity & Risk Assessment</h2>
            {% if data.auth %}
                <div style="display: flex; gap: 20px; align-items: center; margin-bottom: 20px;">
                    <div style="flex: 1;">
                        <h3>Risk Level</h3>
                        {% set risk = data.auth.get('risk_assessment', 'Unknown') %}
                        <span class="risk-badge {{ 'risk-high' if risk|lower in ['high', 'critical'] else 'risk-medium' if risk|lower == 'medium' else 'risk-low' }}">
                            {{ risk|upper }}
                        </span>
                    </div>
                    <div style="flex: 1;">
                        <h3>Bot Probability</h3>
                        <div style="font-size: 24px; font-weight: bold;">{{ (data.auth.get('bot_likelihood', 0) * 100)|round }}%</div>
                    </div>
                </div>
                
                {% if data.auth.get('red_flags') %}
                <h3>Risk Indicators</h3>
                <ul style="font-size: 13px; color: var(--danger); padding-left: 20px;">
                    {% for flag in data.auth.get('red_flags') %}
                    <li>{{ flag }}</li>
                    {% endfor %}
                </ul>
                {% endif %}
            {% else %}
            <p style="color: #94a3b8; font-style: italic;">Authenticity analysis unavailable.</p>
            {% endif %}
        </div>

        <!-- CONSUMER PROFILE -->
        <div class="section">
            <h2>🛍️ Consumer Behavior</h2>
            {% if data.consumer and not data.consumer.error %}
                <h3>Shopping Persona</h3>
                <div class="tag brand" style="font-size: 14px; margin-bottom: 15px;">{{ data.consumer.get('shopping_psychology', {}).get('buyer_persona', 'Unknown') }}</div>
                
                <h3>Brand Affinity</h3>
                <div style="margin-bottom: 15px;">
                {% for brand, affinity in data.consumer.get('brand_relationships', {}).get('brand_loyalty', {}).items() %}
                    <span class="tag brand">{{ brand }}</span>
                {% endfor %}
                </div>

                <h3>Projected Purchases (90 Days)</h3>
                <ul style="font-size: 13px; padding-left: 20px; margin: 0;">
                {% for item in data.consumer.get('forecast_90_day', {}).get('predicted_purchases', []) %}
                    <li>{{ item }}</li>
                {% endfor %}
                </ul>
            {% else %}
                <p style="color: #94a3b8; font-style: italic;">Consumer data processing incomplete.</p>
            {% endif %}
        </div>
    </div>

    <!-- BEHAVIOR & LIFESTYLE (New) -->
    <div class="section">
        <h2>🧬 Behavioral & Lifestyle</h2>
        {% if data.behavior %}
            <div class="grid" style="grid-template-columns: 1fr 1fr 1fr; gap: 20px;">
                <div>
                    <h3>Temperament</h3>
                    <div style="font-weight: bold;">{{ data.behavior.get('temperament', {}).get('label', 'Unknown') }}</div>
                    <p style="font-size: 12px; color: #64748b;">{{ data.behavior.get('temperament', {}).get('description', '') }}</p>
                </div>
                <div>
                    <h3>Relationships</h3>
                    {% if data.behavior.get('relationships', {}).get('gated') %}
                    <div style="font-size: 13px; color: #64748b; font-style: italic;">
                        Not inferred. Relationship and intimacy patterns are sensitive personal data
                        about someone who has not agreed to being analysed.
                    </div>
                    {% else %}
                    <div style="font-size: 13px;">
                        <strong>Style:</strong> {{ data.behavior.get('relationships', {}).get('attachment_style', 'Unknown') }}<br>
                        <strong>Pattern:</strong> {{ data.behavior.get('relationships', {}).get('pattern', 'N/A') }}
                    </div>
                    {% endif %}
                </div>
                <div>
                    <h3>Professional</h3>
                    <div style="font-size: 13px;">
                        <strong>Skill:</strong> {{ data.behavior.get('professional', {}).get('tech_skill_level', 'Unknown') }}<br>
                        <strong>Source:</strong> {{ data.behavior.get('professional', {}).get('earning_source', 'Unknown') }}
                    </div>
                </div>
            </div>
        {% else %}
            <p style="color: #94a3b8; font-style: italic;">Behavioral data unavailable.</p>
        {% endif %}
    </div>

    <div class="page-break"></div>

    <div class="grid">
        <!-- BELIEF SYSTEM -->
        <div class="section">
            <h2>🌍 Worldview & Beliefs</h2>
            {% if data.beliefs and not data.beliefs.error and not data.beliefs.gated %}
                <h3>Political Compass</h3>
                <div style="background: #f8fafc; padding: 15px; border-radius: 8px; margin-bottom: 15px; text-align: center; border: 1px solid #e2e8f0;">
                    <div style="font-weight: bold; color: var(--primary);">{{ data.beliefs.get('POLITICAL COMPASS', {}).get('label', 'Unknown Alignment') }}</div>
                    <div style="font-size: 12px; margin-top: 5px; color: #64748b;">
                        Economic: {{ data.beliefs.get('POLITICAL COMPASS', {}).get('economic_axis', 0) }} | 
                        Social: {{ data.beliefs.get('POLITICAL COMPASS', {}).get('social_axis', 0) }}
                    </div>
                </div>
                
                <h3>Core Values</h3>
                {% for key, val in data.beliefs.get('SOCIAL VALUES', {}).items() %}
                <div style="margin-bottom: 8px;">
                    <div style="display:flex; justify-content:space-between; font-size:12px; font-weight: 500;">
                        <span>{{ key|replace('_', ' ')|title }}</span>
                        <span>{{ val }}/10</span>
                    </div>
                    <div class="bar-container"><div class="bar-fill" style="width: {{ val * 10 }}%; opacity: 0.8;"></div></div>
                </div>
                {% endfor %}
            {% elif data.beliefs.gated %}
                <p style="color: #94a3b8; font-style: italic;">
                    Not inferred. Political and religious opinions are sensitive personal data about
                    someone who has not agreed to being analysed.
                </p>
            {% else %}
                <p style="color: #94a3b8; font-style: italic;">Belief system analysis unavailable.</p>
            {% endif %}
        </div>

        <!-- PSYCHOLOGICAL PROFILE -->
        <div class="section">
            <h2>🧠 Psychological Profile</h2>
            {% if data.psych %}
                <h3>Big 5 Personality Traits</h3>
                {% for trait, score in data.psych.items() %}
                    {% if score is number %}
                    <div style="margin-bottom: 10px;">
                        <div style="display:flex; justify-content:space-between; font-size:12px; font-weight: 500;">
                            <span>{{ trait|title }}</span>
                            <span>{{ (score * 100)|round }}%</span>
                        </div>
                        <div class="bar-container"><div class="bar-fill" style="width: {{ score * 100 }}%; background-color: #f43f5e;"></div></div>
                    </div>
                    {% endif %}
                {% endfor %}
                
                <h3 style="margin-top: 20px;">Communication Style</h3>
                <p style="font-size: 13px; color: #475569;">{{ data.raw.content_analysis.get('communication_style', 'Analysis pending...') }}</p>
            {% else %}
                <p style="color: #94a3b8; font-style: italic;">Deep psychological profiling unavailable.</p>
            {% endif %}
        </div>
    </div>

    <!-- RECENT ACTIVITY (New) -->
    <div class="section">
        <h2>📅 Recent Activity Analysis</h2>
        {% if data.content %}
            <table class="content-table">
                <thead>
                    <tr>
                        <th width="65%">Content / Text</th>
                        <th width="15%">Date</th>
                        <th width="20%">Metrics</th>
                    </tr>
                </thead>
                <tbody>
                    {% for item in data.content %}
                    <tr>
                        <td>
                            <div style="color: #1e293b; margin-bottom: 4px;">{{ item.text or item.title or item.description or 'No text' }}</div>
                        </td>
                        <td style="color: #64748b;">
                            {{ item.created_at[:10] if item.created_at else 'Unknown' }}
                        </td>
                        <td>
                            <div style="font-size: 11px;">
                                {% if item.likes_count %}❤ {{ item.likes_count }}{% endif %}
                                {% if item.view_count %}👁 {{ item.view_count }}{% endif %}
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        {% else %}
            <p style="color: #94a3b8; font-style: italic;">No recent content available for analysis.</p>
        {% endif %}
    </div>

    <!-- DIGITAL FOOTPRINT -->
    <div class="section">
        <h2>🌐 Digital Footprint</h2>
        {% if data.connected_accounts %}
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px;">
            {% for acc in data.connected_accounts %}
            <div style="display: flex; align-items: center; gap: 10px; padding: 10px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0;">
                <div style="width: 32px; height: 32px; background: #e2e8f0; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px; color: #64748b;">
                    {{ acc.platform[0]|upper }}
                </div>
                <div>
                    <div style="font-weight: bold; font-size: 13px;">{{ acc.username }}</div>
                    <div style="font-size: 11px; color: #94a3b8; text-transform: capitalize;">{{ acc.platform }}</div>
                </div>
            </div>
            {% endfor %}
        </div>
        {% else %}
        <p style="color: #94a3b8; font-style: italic;">No connected accounts identified in public footprint.</p>
        {% endif %}
    </div>

    <div class="footer">
        <strong>CONFIDENTIAL DOSSIER</strong><br>
        Generated by VANTA Deep Intelligence Platform<br>
        <span style="font-family: monospace;">HASH: {{ data.meta.analysis_hash or 'N/A' }}</span>
    </div>
</body>
</html>
        """
        return self.env.from_string(html)
