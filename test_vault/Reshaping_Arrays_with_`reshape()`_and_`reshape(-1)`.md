# Reshaping Arrays with `reshape()` and `reshape(-1)`

Reshaping Arrays with `reshape()` and `reshape(-1)`
==================================================

Introduction
------------

* Definition: **reshaping arrays** is a fundamental concept in data science that involves manipulating the dimensions of an array to create new matrices.
* Intuitive Explanation: reshaping arrays can be thought of as rearranging the blocks or tiles of an array into a different shape, while preserving its overall content and structure.
* Properties & Rules: there are no inherent constraints on the number of dimensions or the size of each dimension when reshaping an array; however, it is essential to ensure that the resulting array has a valid data type and dimensionality.
* Syntax & Usage: The `reshape()` function takes two parameters: the original array and the desired shape of the output array. The `reshape(-1)` function, on the other hand, is used when we want to reshape an array by inferring its shape from the number of elements in the input array and the desired number of rows or columns.
* Examples:
  * Reshaping a vector to a matrix using the `reshape()` function:
```
a = np.array([1, 2, 3])
b = reshape(a, (3, 1))
```
The resulting array is now a two-dimensional matrix with three rows and one column.
* Edge cases include using an invalid shape for the output array or passing in the wrong number of elements for `reshape(-1)`.
* Performance Considerations: there is no significant difference between reshaping arrays using `reshape()` or `reshape(-1)`; however, it is essential to ensure that the output array has a valid data type and dimensionality.
* Common Mistakes & Best Practices: avoid passing in invalid shapes for the output array and ensure that the resulting array has a valid data type and dimensionality.
* Use Cases & Applications: reshaping arrays is an essential skill in data science, particularly when working with matrices and tensors. It can be used to quickly rearrange data and make it more accessible or to create new matrices with specific shapes.
* Comparison with Related Concepts: reshaping arrays is similar to other array manipulation functions like `transpose()`, but it differs in that it allows for the creation of new matrices with any desired shape.
* Linking Notes: related notes include data types, matrix operations, and tensor operations.
