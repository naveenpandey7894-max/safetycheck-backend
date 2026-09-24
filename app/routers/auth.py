from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.core.db import prisma
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.schemas.auth import UserRegister, UserLogin, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserOut)
async def register(payload: UserRegister):
    existing = await prisma.user.find_unique(where={"email": payload.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = await prisma.user.create(
        data={
            "name": payload.name,
            "email": payload.email,
            "hashedPassword": hash_password(payload.password),
            "role": payload.role,
            "companyId": payload.company_id,
        }
    )
    return user


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin):
    user = await prisma.user.find_unique(where={"email": payload.email})
    if not user or not verify_password(payload.password, user.hashedPassword):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/token", include_in_schema=False)
async def token_login(form: OAuth2PasswordRequestForm = Depends()):
    user = await prisma.user.find_unique(where={"email": form.username})
    if not user or not verify_password(form.password, user.hashedPassword):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
async def get_me(current_user=Depends(get_current_user)):
    """Returns the currently authenticated user, resolved from the Bearer
    token via get_current_user. Used by the mobile app to show who's
    logged in (header on the Reports/Dashboard tabs)."""
    return current_user












# from fastapi import APIRouter, Depends, HTTPException
# from fastapi.security import OAuth2PasswordRequestForm

# from app.core.db import prisma
# from app.core.security import hash_password, verify_password, create_access_token
# from app.schemas.auth import UserRegister, UserLogin, TokenResponse, UserOut

# router = APIRouter(prefix="/auth", tags=["auth"])

# @router.post("/register", response_model=UserOut)
# async def register(payload: UserRegister):
#     existing = await prisma.user.find_unique(where={"email": payload.email})
#     if existing:
#         raise HTTPException(status_code=400, detail="Email already registered")

#     user = await prisma.user.create(
#         data={
#             "name": payload.name,
#             "email": payload.email,
#             "hashedPassword": hash_password(payload.password),
#             "role": payload.role,
#             "companyId": payload.company_id,
#         }
#     )
#     return user


# @router.post("/login", response_model=TokenResponse)
# async def login(payload: UserLogin):
#     user = await prisma.user.find_unique(where={"email": payload.email})
#     if not user or not verify_password(payload.password, user.hashedPassword):
#         raise HTTPException(status_code=401, detail="Incorrect email or password")

#     token = create_access_token(user.id)
#     return TokenResponse(access_token=token, user=UserOut.model_validate(user))


# @router.post("/token", include_in_schema=False)
# async def token_login(form: OAuth2PasswordRequestForm = Depends()):
#     user = await prisma.user.find_unique(where={"email": form.username})
#     if not user or not verify_password(form.password, user.hashedPassword):
#         raise HTTPException(status_code=401, detail="Incorrect email or password")

#     return {"access_token": create_access_token(user.id), "token_type": "bearer"}