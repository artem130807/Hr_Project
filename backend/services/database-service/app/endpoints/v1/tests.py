from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import Response
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.middleware import get_db
from app.db.v1.models import Test, TestQuestion, CandidateTestResult, CandidateQuestionAnswer
from app.schemas.v1.tests import (
    TestCreate, TestUpdate, TestRead,
    TestQuestionCreate, TestQuestionRead,
    CandidatTestResultCreate, CandidatTestResultRead, TestReadWOQuestions,
    CandidateQuestionAnswerCreate, CandidateQuestionAnswerRead, CandidateQuestionAnswerUpdate,
)


router = APIRouter()


# ---------- TEST CRUD ----------
@router.get("/test/{test_id}", response_model=TestRead)
async def get_test(test_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Test).options(selectinload(Test.questions)).where(Test.id == test_id)
    )
    test = result.scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    return test


@router.get("/tests", response_model=list[TestRead])
async def list_tests(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Test).options(selectinload(Test.questions))
    )
    return result.scalars().all()


@router.post("/test", response_model=TestReadWOQuestions, status_code=status.HTTP_201_CREATED)
async def create_test(data: TestCreate, db: AsyncSession = Depends(get_db)):
    new_test = Test(**data.model_dump())
    new_test.questions = []
    db.add(new_test)
    await db.commit()
    await db.refresh(new_test)
    return new_test


@router.put("/test/{test_id}", response_model=TestReadWOQuestions)
@router.patch("/test/{test_id}", response_model=TestReadWOQuestions)
async def update_test(test_id: int, data: TestUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    updates = data.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(test, key, value)

    await db.commit()
    await db.refresh(test)
    return test


@router.delete("/test/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test(test_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    await db.delete(test)
    await db.commit()
    return None


# ---------- TEST QUESTION CRUD ----------

@router.post("/test/{test_id}/questions", response_model=list[TestQuestionRead])
async def add_questions_endpoint(test_id: int, data: list[TestQuestionCreate], db: AsyncSession = Depends(get_db)):
    # убедимся, что тест существует
    result = await db.execute(select(Test).where(Test.id == test_id))
    test: Test | None = result.scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    
    new_questions = []
    for question in data:
        options = [str(o).strip() for o in (question.options or []) if str(o).strip()]
        correct = question.correct_option_index
        if correct is not None and (not options or correct >= len(options)):
            correct = None
        new_q = TestQuestion(
            text=question.text,
            test_id=test_id,
            options=options or None,
            correct_option_index=correct,
        )
        db.add(new_q)
        new_questions.append(new_q)
    
    await db.commit()
    
    question_ids = [q.id for q in new_questions if hasattr(q, 'id') and q.id is not None]
    
    if question_ids:
        result = await db.execute(
            select(TestQuestion).where(TestQuestion.id.in_(question_ids))
        )
        return result.scalars().all()
    
    return []


@router.put("/test/{test_id}/questions", response_model=list[TestQuestionRead])
async def replace_questions_endpoint(
    test_id: int,
    data: list[TestQuestionCreate],
    db: AsyncSession = Depends(get_db),
):
    """Replace all questions for a test (edit form save)."""
    result = await db.execute(
        select(Test).options(selectinload(Test.questions)).where(Test.id == test_id)
    )
    test = result.scalar_one_or_none()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    test.questions.clear()
    for question in data:
        text = (question.text or "").strip()
        if not text:
            continue
        options = [str(o).strip() for o in (question.options or []) if str(o).strip()]
        correct = question.correct_option_index
        if correct is not None and (not options or correct >= len(options)):
            correct = None
        test.questions.append(
            TestQuestion(
                text=text,
                test_id=test_id,
                options=options or None,
                correct_option_index=correct,
            )
        )
    await db.commit()
    result = await db.execute(
        select(TestQuestion).where(TestQuestion.test_id == test_id).order_by(TestQuestion.id)
    )
    return result.scalars().all()



@router.get("/test/{test_id}/questions", response_model=list[TestQuestionRead], status_code=status.HTTP_200_OK)
async def list_questions_endpoint(test_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TestQuestion).where(TestQuestion.test_id == test_id))
    return result.scalars().all()
    


@router.get("/question/{question_id}", response_model=TestQuestionRead, status_code=status.HTTP_200_OK)
async def get_question_endpoint(question_id: int,
                                db: AsyncSession = Depends(get_db)):
    question = await db.get(TestQuestion, question_id)
    if not question:
        raise HTTPException(404, 'Question not found')
    return question

# ---------- CANDIDATE TEST RESULT CRUD ----------

@router.post("/test/results", response_model=CandidatTestResultRead, status_code=status.HTTP_201_CREATED)
async def create_result_endpoint(data: CandidatTestResultCreate, db: AsyncSession = Depends(get_db)):
    new_result = CandidateTestResult(**data.model_dump())
    try:
        db.add(new_result)
        await db.flush()

        question_ids_subquery = select(TestQuestion.id).where(TestQuestion.test_id == new_result.test_id)

        await db.execute(
            update(CandidateQuestionAnswer)
            .where(CandidateQuestionAnswer.candidate_id == new_result.candidate_id)
            .where(CandidateQuestionAnswer.result_id.is_(None))
            .where(CandidateQuestionAnswer.question_id.in_(question_ids_subquery))
            .values(result_id=new_result.id)
        )

        await db.commit()
        result = await db.execute(
            select(CandidateTestResult)
            .options(
                selectinload(CandidateTestResult.answers).selectinload(CandidateQuestionAnswer.question)
            )
            .where(CandidateTestResult.id == new_result.id)
        )
        return result.scalars().one()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Candidate result already exists") from exc
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create test result") from exc


@router.get("/test/results/{result_id}", response_model=CandidatTestResultRead)
async def get_result_endpoint(result_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CandidateTestResult)
        .options(
            selectinload(CandidateTestResult.answers).selectinload(CandidateQuestionAnswer.question)
        )
        .where(CandidateTestResult.id == result_id)
    )
    res = result.scalars().one_or_none()
    if not res:
        raise HTTPException(status_code=404, detail="Result not found")
    return res


@router.get("/test/{test_id}/results", response_model=list[CandidatTestResultRead])
async def list_results_for_test_endpoint(test_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CandidateTestResult).where(CandidateTestResult.test_id == test_id))
    return result.scalars().all()


# ---------- CANDIDATE QUESTION ANSWERS CRUD ----------


@router.post(
    "/test/question-answers",
    response_model=CandidateQuestionAnswerRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_answer_endpoint(
    data: CandidateQuestionAnswerCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        answer = CandidateQuestionAnswer(**data.model_dump())
        db.add(answer)
        await db.commit()
        result = await db.execute(
            select(CandidateQuestionAnswer)
            .options(selectinload(CandidateQuestionAnswer.question))
            .where(CandidateQuestionAnswer.id == answer.id)
        )
        return result.scalars().one()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Answer already exists for candidate and question") from exc


@router.get("/test/question-answers/{answer_id}", response_model=CandidateQuestionAnswerRead)
async def get_answer_endpoint(answer_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CandidateQuestionAnswer)
        .options(selectinload(CandidateQuestionAnswer.question))
        .where(CandidateQuestionAnswer.id == answer_id)
    )
    answer = result.scalars().one_or_none()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    return answer


@router.patch("/test/question-answers/{answer_id}", response_model=CandidateQuestionAnswerRead)
async def update_answer_endpoint(
    answer_id: int,
    data: CandidateQuestionAnswerUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CandidateQuestionAnswer)
        .options(selectinload(CandidateQuestionAnswer.question))
        .where(CandidateQuestionAnswer.id == answer_id)
    )
    answer = result.scalars().one_or_none()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")

    payload = data.model_dump(exclude_unset=True)
    if not payload:
        return answer

    for field, value in payload.items():
        setattr(answer, field, value)

    try:
        await db.commit()
        result = await db.execute(
            select(CandidateQuestionAnswer)
            .options(selectinload(CandidateQuestionAnswer.question))
            .where(CandidateQuestionAnswer.id == answer.id)
        )
        return result.scalars().one()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Answer already exists for candidate and question") from exc


@router.delete("/test/question-answers/{answer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_answer_endpoint(answer_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(CandidateQuestionAnswer).where(CandidateQuestionAnswer.id == answer_id)
    )
    answer = result.scalars().one_or_none()
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")

    await db.delete(answer)
    await db.commit()
    return None


@router.get(
    "/test/results/{result_id}/answers",
    response_model=list[CandidateQuestionAnswerRead],
)
async def list_answers_for_result_endpoint(
    result_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CandidateQuestionAnswer)
        .options(selectinload(CandidateQuestionAnswer.question))
        .where(CandidateQuestionAnswer.result_id == result_id)
    )
    return result.scalars().all()


# ---------- TEST RESULT IMAGE ----------

@router.post("/test/results/{result_id}/image", status_code=status.HTTP_204_NO_CONTENT)
async def upload_test_result_image(
    result_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CandidateTestResult).where(CandidateTestResult.id == result_id)
    )
    test_result = result.scalar_one_or_none()
    if not test_result:
        raise HTTPException(status_code=404, detail="Result not found")

    image_bytes = await file.read()
    test_result.image_data = image_bytes
    test_result.image_content_type = file.content_type or "image/jpeg"
    test_result.has_image = True
    await db.commit()


@router.get("/test/results/{result_id}/image")
async def get_test_result_image(
    result_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CandidateTestResult).where(CandidateTestResult.id == result_id)
    )
    test_result = result.scalar_one_or_none()
    if not test_result:
        raise HTTPException(status_code=404, detail="Result not found")
    if not test_result.image_data:
        raise HTTPException(status_code=404, detail="No image for this result")

    return Response(
        content=test_result.image_data,
        media_type=test_result.image_content_type or "image/jpeg",
    )
