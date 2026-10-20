"""Agentic workflow (LangGraph):

    employee message -> classify
        MY_DATA -> answer from the employee's own records (leave balance, request status)
        HR      -> answer from the knowledge base (RAG)
        IT      -> self-help steps from the IT guide (RAG) + IT ticket for this employee,
                   emailed to HR, waiting for HR approval in the admin panel
"""
import re
from typing import TypedDict

from langgraph.graph import END, StateGraph

from .database import get_user, list_requests, log_chat
from .llm import get_llm, invoke_llm
from .rag import answer_from_kb
from .services import submit_request


class State(TypedDict, total=False):
    query: str
    user: dict
    intent: str
    answer: str
    ticket: dict


IT_WORDS = ["wifi", "wi-fi", "laptop", "computer", "vpn", "printer", "password",
            "login", "log in", "software", "internet", "technical", "not working",
            "error", "email", "outlook", "install", "network", "keyboard", "mouse", "monitor"]
URGENT_WORDS = ["urgent", "asap", "immediately", "critical", "can't work", "cannot work"]
MY_DATA_PATTERN = re.compile(
    r"\bmy (leave|leaves|balance|request|requests|ticket|tickets|profile|details)\b|leave balance|"
    r"(how many|remaining|left).{0,25}(leave|leaves)|status of my|my .{0,15}status|"
    r"(leaves?|days?) (do|have) i (have|left)", re.I)
APPLY_PATTERN = re.compile(r"\b(apply|applying|request|want|need|take)\b.{0,30}\b(leave|wfh|work from home|off)\b", re.I)
GUEST = {"email": "guest@local", "full_name": "Guest", "department": "", "role": "employee"}


def heuristic(query):
    q = query.lower()
    return "IT" if any(w in q for w in IT_WORDS) else "HR"


def priority_for(query):
    q = query.lower()
    return "High" if any(w in q for w in URGENT_WORDS) else "Medium"


def classify(state):
    if MY_DATA_PATTERN.search(state["query"]):
        return {"intent": "MY_DATA"}
    if not get_llm():
        return {"intent": heuristic(state["query"])}
    try:
        result = invoke_llm(
            "Classify the employee message as exactly HR or IT.\n"
            "HR = questions about company policy, leave, public holidays, holiday calendar, attendance, "
            "work from home, benefits, payroll, salary, expenses, reimbursement, onboarding or how to raise requests.\n"
            "IT = the employee reports a technical problem or needs technical help: laptop, Wi-Fi, internet, VPN, "
            "password reset, software, printer, email or system access.\n"
            "Return only the single word HR or IT.\nMessage: " + state["query"]
        ).strip().upper()
        return {"intent": "IT" if result.startswith("IT") else "HR"}
    except Exception:
        return {"intent": heuristic(state["query"])}


def my_data_node(state):
    user = get_user(state.get("user", {}).get("email", "")) or state.get("user") or GUEST
    if user.get("email") == GUEST["email"]:
        return {"answer": "Please log in to see your leave balance and requests."}
    lines = [f"Here are your details, **{user['full_name']}**:", "",
             "**Leave balance**",
             f"- Annual Leave: **{user['annual_leave']:g}** day(s)",
             f"- Sick Leave: **{user['sick_leave']:g}** day(s)",
             f"- Casual Leave: **{user['casual_leave']:g}** day(s)"]
    reqs = list_requests(user_email=user["email"])
    lines += ["", f"**Your requests** ({len(reqs)} total)"]
    if reqs:
        for r in reqs[:5]:
            comment = f" — HR: _{r['admin_comment']}_" if r["admin_comment"] else ""
            lines.append(f"- {r['request_id']} · {r['category']} · {r['subject']} → **{r['status'].title()}**{comment}")
        if len(reqs) > 5:
            lines.append("- …see **My Requests** for the full list.")
    else:
        lines.append("- You have not raised any requests yet.")
    return {"answer": "\n".join(lines)}


def hr_node(state):
    answer = answer_from_kb(state["query"], mode="HR")
    if APPLY_PATTERN.search(state["query"]):
        answer += ("\n\n👉 **To apply**, open **Raise a Request** → choose **Leave** (or **Work From Home**), "
                   "pick your dates and submit. HR is notified by email automatically.")
    return {"answer": answer}


def it_node(state):
    user = state.get("user") or GUEST
    try:
        self_help = answer_from_kb(state["query"], mode="IT")
    except Exception:
        self_help = ""
    ticket, email_ok, email_msg = submit_request(
        user, "IT Support", subject=state["query"][:120], details=state["query"],
        priority=priority_for(state["query"]), source="chat")
    notified = ("HR/IT has been notified by email." if email_ok
                else "HR/IT can see it in the admin panel.")
    ticket_msg = (
        f"🎫 IT ticket **{ticket['request_id']}** has been created for you "
        f"(priority: {ticket['priority']}). {notified}\n\n"
        "Status: **PENDING** — track it under **My Requests**."
    )
    answer = (f"**Try these steps first:**\n\n{self_help}\n\n---\n\n{ticket_msg}"
              if self_help else ticket_msg)
    return {"ticket": ticket, "answer": answer}


def route(state):
    return state["intent"]


builder = StateGraph(State)
builder.add_node("classify", classify)
builder.add_node("my_data", my_data_node)
builder.add_node("hr", hr_node)
builder.add_node("it", it_node)
builder.set_entry_point("classify")
builder.add_conditional_edges("classify", route, {"MY_DATA": "my_data", "HR": "hr", "IT": "it"})
builder.add_edge("my_data", END)
builder.add_edge("hr", END)
builder.add_edge("it", END)
GRAPH = builder.compile()


def run_chat(query, user=None):
    result = GRAPH.invoke({"query": query, "user": user or GUEST})
    try:
        log_chat((user or GUEST).get("email", ""), query, result.get("intent", ""))
    except Exception as exc:
        print("Could not log chat:", exc)
    return result
