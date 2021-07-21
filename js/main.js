// humbergerメニュー
$(function () {
    $('.hamburger').click(function() {
        $(this).toggleClass('active');

        if ($(this).hasClass('active')) {
            $('.globalMenuSp').addClass('active');
        } else {
            $('.globalMenuSp').removeClass('active');
        }
    });
});

// 年齢自動計算
function getAge() {
    // window.onload = function getAge() {
    var today = new Date();
    var birthday = new Date( 19880927 );
    var tdate = ( today.getFullYear() * 10000 ) + (( today.getMonth() + 1 ) * 100 ) + today.getDate() ;
    var ageR = Math.floor((tdate - birthday) / 10000);
    // console.log( Math.floor(( tdate - birthday ) / 10000 )) ;
    return ageR;
}

const age = document.getElementById('age');
age.textContent = getAge() + "歳";
