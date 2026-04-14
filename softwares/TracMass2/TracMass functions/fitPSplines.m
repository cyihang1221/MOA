function [a, gcv, yhat] = fitPSplines(y,B,pord,lambda)
%Magnus Åberg
[m n] = size(B);
D = diff(eye(n), pord);
a = (B' * B + lambda * D' * D) \ (B' * y);
yhat = B * a;
Q = inv(B' * B + lambda * D' * D);
s = sum((y - yhat) .^ 2);
t = sum(diag(Q * (B' * B)));
gcv = s / (m - t)^2;