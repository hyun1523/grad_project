import streamlit as st

from core import auth


def render() -> None:
    _, center, _ = st.columns([1, 2, 1])
    with center:
        tab_login, tab_register = st.tabs(["🔑 로그인", "📝 회원가입"])

        with tab_login:
            with st.form("login_form"):
                username = st.text_input("아이디")
                password = st.text_input("비밀번호", type="password")
                submitted = st.form_submit_button("로그인")
            if submitted:
                user = auth.login(username, password)
                if user:
                    st.session_state.user = user
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 올바르지 않아요.")

        with tab_register:
            with st.form("register_form"):
                new_name = st.text_input("아이디 (3~20자, 한글/영문/숫자/_)")
                new_pw = st.text_input("비밀번호 (6자 이상)", type="password")
                new_pw2 = st.text_input("비밀번호 확인", type="password")
                submitted = st.form_submit_button("회원가입")
            if submitted:
                if new_pw != new_pw2:
                    st.error("비밀번호 확인이 일치하지 않아요.")
                else:
                    ok, msg = auth.register(new_name, new_pw)
                    (st.success if ok else st.error)(msg)
