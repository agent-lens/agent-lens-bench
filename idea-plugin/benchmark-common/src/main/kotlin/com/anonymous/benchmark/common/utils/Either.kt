package com.anonymous.benchmark.common.utils

sealed class Either<out L, out R>

inline fun <L, R, T> Either<L, R>.map(mapper: (R) -> T): Either<L, T> = when (this) {
    is Left<L> -> this
    is Right<R> -> Right(mapper(value))
}

inline fun <L, R> Either<L, R>.recover(recoverer: (L) -> R): R = when (this) {
    is Left<L> -> recoverer(failure)
    is Right<R> -> value
}

data class Left<out L>(val failure: L): Either<L, Nothing>()
data class Right<out R>(val value: R): Either<Nothing, R>()
